import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
import json
from opencage.geocoder import OpenCageGeocode
from streamlit_option_menu import option_menu
import ast  
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from streamlit_authenticator import Authenticate
import hashlib
import os
from dotenv import load_dotenv


load_dotenv()
opencage_api_key = os.getenv("opencage_api_key")
geolocator = OpenCageGeocode(opencage_api_key)

if "user_id" not in st.session_state:
    st.session_state.user_id=0
if "table_name" not in st.session_state:
    st.session_state.table_name = ""

if "workspace_name" not in st.session_state:
    st.session_state.workspace_name = ""
if "result" not in st.session_state:
    st.session_state.result = None
if "selected" not in st.session_state:
    st.session_state.selected = None  
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

#Function to create a workspace
def create_workspace(id, workspace_name,user_id):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()
    workspace_created = False
    try:
        cursor.execute("INSERT INTO workspaces (id, workspace_name,user_id) VALUES (%s, %s,%s) RETURNING id;", (id, workspace_name,user_id))
        workspace_id = cursor.fetchone()[0]
        connection.commit()
        st.success(f'Workspace "{workspace_name}" created successfully .')
        workspace_created = True
    except psycopg2.errors.UniqueViolation as e:

        connection.rollback()
        st.info(f'Workspace "{workspace_name}" already exists. Please choose a different workspace name.')
        workspace_id = None

    except Exception as e:
        connection.rollback()
        st.warning(f'Error creating workspace: {e}')
        workspace_id = None
    finally:
        connection.close()

    return workspace_created,workspace_id,user_id


# Function to retrieve workspace history
def get_workspace_history(user_id):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    print("User id inside get_workspace_history",user_id)
    # Retrieve workspace history
    cursor.execute(f"SELECT DISTINCT workspace_name FROM workspace_history WHERE user_id={user_id};")
    workspace_history = cursor.fetchall()
    st.session_state.user_id = user_id

    print("workspace_history ",workspace_history)

    connection.close()

    return workspace_history

#Function to create table
def create_dynamic_table(table_name, columns, data):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    columns_lower = [col.lower().replace(' ', '_') for col in columns]
    columns_lower += ["id", "location"]

    if "id" not in columns_lower:
        columns_lower = ["id"] + columns_lower

    if "location" not in columns_lower:
        columns_lower += ["location"]

    if 'id' not in data.columns:
        data['id'] = np.random.randint(1, 1000, size=len(data))

    if 'location' not in data.columns:
        data['location'] = ''

    column_definitions = ", ".join([f'"{col}" VARCHAR' for col in columns_lower])
    
    create_table_query = f"CREATE TABLE IF NOT EXISTS {table_name} ({column_definitions});"
    cursor.execute(create_table_query)

    col_dict=dict()
    for name in columns_lower:
        if name in ['address','address_line1','address_line2']:
            col_dict['address']=name
        if name in ['city']:
            col_dict['city']=name
        if name in ['state']:
            col_dict['state']=name
        if name in ['zipcode']:
            col_dict['zipcode']=name
        if name in ['county' ,'country']:
            col_dict['country']=name
        
    for idx, row in data.iterrows():
        row["id"] = idx + 1


        required_columns = ['address', 'state', 'city', 'zipcode', 'country']
    
        if any(col in data.columns for col in required_columns) and all(col in row.index for col in col_dict.values()):
            # latitude, longitude = update_location(row[col_dict['address']], row[col_dict['city']], row[col_dict['state']], row[col_dict['zipcode']], row[col_dict['country']])
            latitude,longitude=update_location(row)
            # row["location"] += f" ({latitude}, {longitude})" 
            if latitude is not None and longitude is not None:
                row["location"] += f" ({latitude}, {longitude})"
            else:
                row["location"] += " (0, 0)"
        else:
            print("Skipping row due to missing location-related columns.")
        values = "', '".join(str(row[col]) for col in columns_lower if col in row.index)
        insert_query = f"INSERT INTO {table_name} ({', '.join(columns_lower)}) VALUES ('{values}');"

        print(insert_query)
        cursor.execute(insert_query)

    connection.commit()
    connection.close()


# Function to fetch data from a table in the database
def fetch_data(table_name):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    query = f"SELECT * FROM {table_name} ORDER BY ID ASC;"
    cursor.execute(query)
    data = cursor.fetchall()

    column_names = [desc[0] for desc in cursor.description]

    connection.close()

    return pd.DataFrame(data, columns=column_names)

# Function to update data in a table in the database
def update_data(original_data, updated_data, table_name, columns):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    for index, row in updated_data.iterrows():
        original_row = original_data.iloc[index]

        if not row.equals(original_row):
            update_location_in_db(cursor, row, table_name, columns)

    connection.commit()
    connection.close()

# Function to update location in the database
def update_location_in_db(cursor, row, table_name, columns):
    col_dict = dict()
    for name in columns:
        if name in ['address', 'address_line1', 'address_line2']:
            col_dict['address'] = name
        if name in ['city']:
            col_dict['city'] = name
        if name in ['state']:
            col_dict['state'] = name
        if name in ['zipcode']:
            col_dict['zipcode'] = name
        if name in ['county', 'country']:
            col_dict['country'] = name

    latitude, longitude = update_location(row)

    if latitude is not None and longitude is not None:
        new_location_value = f"({latitude}, {longitude})"
        update_columns = [f"{col} = '{row[col]}'" for col in columns if col in row.index and col != 'location']
        update_columns.append(f"location = '{new_location_value}'")

        update_columns_str = ', '.join(update_columns)

        query = f"UPDATE {table_name} SET {update_columns_str} WHERE id = '{row['id']}';"
        print("Update Query:", query)
        cursor.execute(query)

# Function to update location based on address-related columns
def update_location(row):
    address_columns = ['address', 'address_line1', 'address_line2']
    location_columns = ['city', 'state', 'zipcode', 'country']

    address = ', '.join(str(row[col]) for col in address_columns if col in row.index)
    location = ', '.join(str(row[col]) for col in location_columns if col in row.index)
    full_address = f"{address}, {location}"

    location_data = geolocator.geocode(full_address)

    if location_data and 'geometry' in location_data[0]:
        geometry = location_data[0]['geometry']
        return geometry['lat'], geometry['lng']
    else:
        return 0, 0

# def fetch_global_headers_from_database(workspace_name):
#     connection_params = {
#         'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
#         'port': '5432',
#         'database': 'postgres',
#         'user': 'postgres',
#         'password': 'postgres'
#     }

#     connection = psycopg2.connect(**connection_params)
#     cursor = connection.cursor()
#     print("workspace_name in thefetch ",workspace_name)
#     query = f"SELECT global_headers FROM workspaces WHERE workspace_name= '{workspace_name}';"

#     cursor.execute(query)
#     result = cursor.fetchone()
    

#     print("result",result)
#     if result is not None:
#         global_headers_str = result[0]
#         global_headers_list = [header.strip() for header in global_headers_str[0:-1].split(',')]
#     else:
#         # Handle the case where no results are found (e.g., return an empty list)
#         global_headers_list = []

#     cursor.close()
#     connection.close()

#     return global_headers_list

# def update_json_mapping_in_database(workspace_name,table_name, global_headers, selected_columns):
#     connection_params = {
#         'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
#         'port': '5432',
#         'database': 'postgres',
#         'user': 'postgres',
#         'password': 'postgres'
#     }

#     connection = psycopg2.connect(**connection_params)
#     cursor = connection.cursor()

   
#     mapping_json = json.dumps(dict(zip(global_headers, selected_columns)))
    
#     update_query = f"UPDATE workspaces SET table_name = %s WHERE workspace_name = %s;"
    
#     cursor.execute(update_query,(table_name,workspace_name))
#     update_query = f"UPDATE workspaces SET mapping_json = %s WHERE table_name = %s;"
#     cursor.execute(update_query, (mapping_json, table_name))

#     # insert_query = f"INSERT INTO workspaces (workspace_name,table_name,mapping_json) VALUES('{workspace_name}','{table_name}','{mapping_json}');"
    
#     # cursor.execute(insert_query)

#     connection.commit()
#     cursor.close()
#     connection.close()


# def save_global_headers(workspace_name, global_headers_input):
#     connection_params = {
#         'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
#         'port': '5432',
#         'database': 'postgres',
#         'user': 'postgres',
#         'password': 'postgres'
#     }

#     connection = psycopg2.connect(**connection_params)
#     cursor = connection.cursor()

#     update_query = "UPDATE workspaces SET global_headers = %s WHERE workspace_name = %s;"
#     cursor.execute(update_query, (global_headers_input, workspace_name))
#     # st.success("Global Headers saved successfully!")


#     connection.commit()
#     cursor.close()
#     connection.close()


def update_table_name(workspace,table_name,user_id,file_name):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    insert_query=f"INSERT INTO workspace_history (workspace_name,table_name,user_id,filename) VALUES('{workspace}','{table_name}','{user_id}','{file_name}');"
    
    cursor.execute(insert_query)
    # st.success("Global Headers saved successfully!")


    connection.commit()
    cursor.close()
    connection.close()
def insert_user_credentials(username, password):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    try:
        connection = psycopg2.connect(**connection_params)
        cursor = connection.cursor()


        hashed_password = hash_password(password)

        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s);", (username, hashed_password))

        connection.commit()
        cursor.close()
        connection.close()

        return True
    except Exception as e:
        print(f"Error inserting user credentials: {e}")
        return False
    
def hash_password(password):
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    print("*********",hashed_password)
    return hashed_password

def fetch_user_credentials(username, password):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    try:
        connection = psycopg2.connect(**connection_params)
        cursor = connection.cursor()

        # Fetch hashed password from the 'users' table for the provided username
        cursor.execute("SELECT user_id,password FROM users WHERE username = %s;", (username,))
        user_data = cursor.fetchone()
        
        print("userdata",user_data)
        cursor.close()
        connection.close()
        user_id,hashed_password=user_data
        print("User id inside the fetch_user_credentials",user_id)
  
        print(verify_password(password, hashed_password))
        if verify_password(password, hashed_password):
            return True,user_id
        else:
            return False,user_id

    except Exception as e:
        print(f"Error fetching user credentials: {e}")
        return False,user_id
    
def verify_password(input_password, hashed_password):
    print(input_password,hashed_password,hash_password(input_password))
    print(type(hashed_password),type(hash_password(input_password)))
    return hash_password(input_password) == hashed_password

def add_value_labels(ax, spacing=5):
    for rect in ax.patches:
        y_value = rect.get_y() + rect.get_height() / 2
        x_value = rect.get_width()
        label = "{:.2f}".format(x_value)
        ax.text(x_value + spacing, y_value, label, ha="center", va="center")

def customize_x_axis_scale(ax):
    ax.set_xlim(0, ax.get_xlim()[1] * 1.2)  
    ax.get_xaxis().get_major_formatter().set_scientific(False)

    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha='right')
    # ax.set_xticks(range(len(df.columns)))
    # ax.set_xticklabels([f'{float(label)/1e6:.2f}M' for label in df.columns])
    # # ax.set_xticklabels([f'{float(df.loc[label][col])/1e6:.2f}M' for label in df.index for col in df.columns])











with st.sidebar:
    st.image("genpactlogo.png")
    selected = option_menu("EXPOSURE MANAGEMENT", ["SignUP","Login Page","Workspaces", "Data Upload", 'Update Data','Analytics'], menu_icon="chevron-down", default_index=0)

st.session_state.result = None


if selected=="SignUP":
    st.header("Signup")
    new_username = st.text_input("Enter a new username:")
    new_password = st.text_input("Enter a new password:", type='password')
    confirm_password = st.text_input("Confirm password:", type='password')

    if st.button('Signup'):
        if new_password == confirm_password:
            print(new_password)
            if insert_user_credentials(new_username, new_password):
                st.success("Signup successful. You can now log in.")
            else:
                st.error("Error during signup. Please try again.")
        else:
            st.error("Passwords do not match. Please enter matching passwords.")

if selected=="Login Page":
    st.header("Login Page")
    username_input = st.text_input("Username:")
    password_input = st.text_input("Password:", type='password')

    if st.button('Login'):
        # Fetch user data from PostgreSQL
        user_data,user_id = fetch_user_credentials(username_input, password_input)
        print("user------------",user_data,user_id)
        st.session_state.user_id = user_id
        if user_data:
            # st.title(f'Welcome *{user_data["name"]}*')
            st.write("You have successfully Logged In!")
        else:
            st.error('Username/password is incorrect')

if st.session_state.user_id !=0:
    # 'Workspaces' section
    if selected == 'Workspaces':
        workspace_name = st.text_input("Enter Workspace Name")
        # global_headers_input = st.text_input("Enter Global Headers (comma-separated):")
        workspace_created = st.session_state.get('workspace_created', False)
        user_id=st.session_state.user_id 
        print("User_id from Workspace section",user_id)

        
        if st.button('Create Workspace', key='create_workspace_button'):
            try:
                connection_params = {
                    'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
                    'port': '5432',
                    'database': 'postgres',
                    'user': 'postgres',
                    'password': 'postgres'
                }
                connection = psycopg2.connect(**connection_params)
                cursor = connection.cursor()
                cursor.execute("SELECT MAX(id) FROM workspaces;")
                latest_user_id = cursor.fetchone()[0]
                id = 1 if latest_user_id is None else latest_user_id + 1
                st.session_state.workspace_name = workspace_name
                workspace_created, workspace_id ,user_id= create_workspace(id, workspace_name,user_id)

                # global_headers_input = st.text_input("Enter Global Headers (comma-separated):")
                # print("function before call")
                # print("workspace name ...........",workspace_name)
                # print("global -----------",global_headers_input)
                # # save_global_headers(workspace_name, global_headers_input)
                # print("executed...............")
                        

            except ValueError as e:
                st.warning(str(e))
            finally:
                connection.close()
                print("------------------",workspace_created)
    

        # global_headers_input = st.text_input("Enter Global Headers (comma-separated):")

        # if st.button('Save Global Headers', key='save_headers_button') and global_headers_input:
        #     print("function before call")
        #     print("workspace name ...........",workspace_name)
        #     print("global -----------",global_headers_input)
        #     save_global_headers(workspace_name, global_headers_input)
        #     print("executed...............")
        st.write("### Workspace History")
        
        if workspace_created:
            st.info("You've created a new workspace. Workspace history selection is disabled.")
            workspace_created=True
            st.session_state.workspace_name = workspace_name

        else:
            user_id=st.session_state.user_id
            workspace_history = get_workspace_history(user_id)
            formatted_workspaces = [workspace[0].strip("()").replace(",", "") for workspace in workspace_history]
            selected_workspace = st.selectbox("Select Workspace:", formatted_workspaces, key='workspace_dropdown')

            if selected_workspace:
                user_id=st.session_state.user_id
                # selected_workspace = st.experimental_get_query_params().get('selected', [None])[0]

                connection_params = {
                        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
                        'port': '5432',
                        'database': 'postgres',
                        'user': 'postgres',
                        'password': 'postgres'
                    }
                connection = psycopg2.connect(**connection_params)
                cursor = connection.cursor()
                
                cursor.execute(f"SELECT filename, table_name FROM workspace_history WHERE user_id={user_id} AND workspace_name='{selected_workspace}';")
                files_and_tables = cursor.fetchall()

                # st.write(f"You selected workspace: {selected_workspace}")


                cursor.execute(f"SELECT DISTINCT filename FROM workspace_history WHERE user_id={user_id} AND workspace_name='{selected_workspace}';")
                available_files = [row[0] for row in cursor.fetchall()]


                selected_file = st.selectbox("Select File:", available_files, key='file_dropdown')       
                # st.session_state.selected = 'Update Data'
                st.experimental_set_query_params(selected=selected_workspace,selected_file=selected_file)


    if selected == 'Data Upload':
        uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])
        
        workspace_name=st.session_state.workspace_name
        user_id=st.session_state.user_id
        if uploaded_file is not None:
            file_name = uploaded_file.name
            file_info = pd.ExcelFile(uploaded_file)

            st.write("### Sheet Names")
            sheet_names = file_info.sheet_names
            selected_sheet = st.selectbox("Select Sheet:", sheet_names, key='sheet_dropdown')
            
            data = pd.read_excel(file_info, sheet_name=selected_sheet)
            file_name=file_name.replace(' ','_').replace('.xlsx','')
            #  filename_sheetname
            file_name=f"{file_name}_{selected_sheet}"
            st.session_state.uploaded_file_name = file_name
            data.columns = [col.lower().replace(' ', '_').replace('/','') for col in data.columns]

            st.write("### Select Attributes")
            all_columns_option = "Select All"
            selected_columns = st.multiselect("Columns", [all_columns_option] + data.columns.tolist())

            if all_columns_option in selected_columns:
                selected_columns = data.columns.tolist()

            # # updated_data = st.data_editor(data)
            
            # selected_columns = st.multiselect("Columns", data.columns.tolist())

            if st.button('Submit', key='create_table_button') and selected_columns:
                table_name = f"table{np.random.randint(100)}"
                create_dynamic_table(table_name, selected_columns, data)
                update_table_name(workspace_name, table_name,user_id,file_name)
                st.success(f'Submitted Successfully!')
                st.session_state.table_name = table_name
            # Retrieve the workspace name from session state
            workspace_name = st.session_state.workspace_name
            # st.session_state.table_name = table_name

            st.experimental_set_query_params(selected=workspace_name)

    if selected == 'Update Data' or st.session_state.selected == 'Update Data':
            user_id=st.session_state.user_id
            workspace_name = st.session_state.workspace_name
            selected_workspace = st.experimental_get_query_params().get('selected', [None])[0]

            connection_params = {
                    'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
                    'port': '5432',
                    'database': 'postgres',
                    'user': 'postgres',
                    'password': 'postgres'
                }
            connection = psycopg2.connect(**connection_params)
            cursor = connection.cursor()
            
            # cursor.execute(f"SELECT filename, table_name FROM workspace_history WHERE user_id={user_id} AND workspace_name='{selected_workspace}';")
            # files_and_tables = cursor.fetchall()

            # st.write(f"You selected workspace: {selected_workspace}")


            # cursor.execute(f"SELECT DISTINCT filename FROM workspace_history WHERE user_id={user_id} AND workspace_name='{selected_workspace}';")
            # available_files = [row[0] for row in cursor.fetchall()]


            # selected_file = st.selectbox("Select File:", available_files, key='file_dropdown')
            selected_file_query = st.experimental_get_query_params().get('selected_file', [None])[0]
            selected_file = selected_file_query or st.session_state.uploaded_file_name

            # selected_file = st.experimental_get_query_params().get('selected_file', [None])[0]
            # selected_file = st.session_state.uploaded_file_name

            st.title(selected_workspace or workspace_name)
            st.write(f"Sheet Name: {selected_file}")


            cursor.execute(f"SELECT table_name FROM workspace_history WHERE user_id={user_id} AND workspace_name='{selected_workspace}' AND filename='{selected_file}';")
            selected_table = cursor.fetchone()[0]


            # st.write(f"Associated Table Name: {selected_table}")

            
            table_data = fetch_data(selected_table)

            if table_data.empty:
                st.warning(f'Table "{selected_table}" not found.')
            else:
                location_col_index = table_data.columns.get_loc('location')
                print(location_col_index)

                styled_data = table_data.style.apply(lambda x: ['background-color: green' if i == location_col_index else '' for i in range(len(x))])

                st.write("### Data")
                updated_data = st.data_editor(data=table_data)
                
 
                # st.write("### Data")
                # location_col_index = table_data.columns.get_loc('location') + 1  # Adjust for 1-based indexing

                # # Apply custom styling to the 'location' column
                # styled_data = (
                # f'<style> .data-editor-col-{location_col_index} {{ background-color: green; }} </style>'
                # )
                # st.markdown(styled_data, unsafe_allow_html=True)
                # updated_data = st.data_editor(data=table_data)
                
                if st.button('Update', key='save_changes_button'):
                    update_data(table_data, updated_data, selected_table, table_data.columns)
                    st.rerun()
                    st.success('Updated successfully!')

                download_button = st.download_button(
                    label="Download",
                    data=updated_data.to_csv(index=False).encode('utf-8'),
                    file_name=f"updated_data_{selected_table}.csv",
                    key='download_button'
                )
    if selected=="Analytics":
        RegionPeril=['Expense Load','Benchmark Premium']
        Total_2023=[129534.8469,424704.416]
        Total_2024=[129534.8469,424704.416]
        df = pd.DataFrame({"2023": Total_2023, "2024": Total_2024}, index=RegionPeril)
        st.subheader("Expense and Benchmark Premium")
        # st.pyplot(df.plot.barh(stacked=True).figure)
        ax_expense = df.plot.barh(stacked=True).axes
        # add_value_labels(ax_expense)
        customize_x_axis_scale(ax_expense)
        st.pyplot(ax_expense.figure)

        RegionPeril=['PML_100','PML_200','PML_250','PML_500','PML_1000','PML_5000','PML_10000']
        Caribbean_WS_2024=[0,997.4620521,7419.063574,21441.58958,45640.72319,210895.263,472065.0367]
        Caribbean_WS_2023=[0,997.4620521,7419.063574,21441.58958,45640.72319,210895.263,472065.0367]
        Gulf_WS_2024=[0,875.4702494,5507.581388,21299.47437,53449.20346,1354916.444,2482467.437]
        Gulf_WS_2023=[0,875.4702494,5507.581388,21299.47437,53449.20346,1354916.444,2482467.437]
        Mid_Atlantic_WS_2024=[0,0,0,0,8368.179776,148009.3684,3764710.831]
        Mid_Atlantic_WS_2023=[0,0,0,0,8368.179776,148009.3684,3764710.831]
        Northeast_WS_2024=[0,0,0,0,0,11800.41176,41404.72609]	
        Northeast_WS_2023=[0,0,0,0,0,11800.41176,41404.72609]
        Southeast_WS_2024=[5534576.412,10197016.26,11847840.73,15965175.35,19311136.71,25149224.32,25268754.06]
        Southeast_WS_2023=[5534576.412,10197016.26,11847840.73,15965175.35,19311136.71,25149224.32,25268754.06]
        US_OW_2023=[9968.92673,17882.01069,20114.31658,30425.58091,50556.70339,98899.71806,1087589.49]
        US_OW_2024=[9968.92673,17882.01069,20114.31658,30425.58091,50556.70339,98899.71806,1087589.49]	
        US_WiS_2023=[39111.23722,45075.10115,47872.22547,53177.6549,59620.88419,93234.0313,112586.4406]
        US_WiS_2024=[39111.23722,45075.10115,47872.22547,53177.6549,59620.88419,93234.0313,112586.4406]
        # for col in [Caribbean_WS_2024, Caribbean_WS_2023, Gulf_WS_2024, Gulf_WS_2023, 
        #     Mid_Atlantic_WS_2024, Mid_Atlantic_WS_2023, Northeast_WS_2024, 
        #     Northeast_WS_2023, Southeast_WS_2024, Southeast_WS_2023, 
        #     US_OW_2023, US_OW_2024, US_WiS_2023, US_WiS_2024]:
        #     for i in range(len(col)):
        #         col[i] /=  1000000
        
        df = pd.DataFrame({
    "Caribbean WS_2024": Caribbean_WS_2024, 
    "Caribbean WS_2023": Caribbean_WS_2023,
    "Gulf WS_2024": Gulf_WS_2024,
    "Gulf WS_2023": Gulf_WS_2023,
    "Mid Atlantic WS_2024": Mid_Atlantic_WS_2024,
    "Mid Atlantic WS_2023": Mid_Atlantic_WS_2023,
    "Northeast WS_2024": Northeast_WS_2024,
    "Northeast WS_2023": Northeast_WS_2023,
    "Southeast WS_2024": Southeast_WS_2024,
    "Southeast WS_2023": Southeast_WS_2023,
    "US OW_2023": US_OW_2023,
    "US OW_2024": US_OW_2024,
    "US WiS_2023": US_WiS_2023,
    "US WiS_2024": US_WiS_2024}, index=RegionPeril)
        st.subheader("PML Values for Different Regions")
        # st.pyplot(df.plot.barh(stacked=True).figure)
        ax_expense = df.plot.barh(stacked=True).axes
        # add_value_labels(ax_expense)
        customize_x_axis_scale(ax_expense)
        st.pyplot(ax_expense.figure,use_container_width=True)



            