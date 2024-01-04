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




opencage_api_key = "25d4749b39114fdb9898642ddb1db305"
geolocator = OpenCageGeocode(opencage_api_key)

if "table_name" not in st.session_state:
    st.session_state.table_name = ""

if "workspace_name" not in st.session_state:
    st.session_state.workspace_name = ""
if "result" not in st.session_state:
    st.session_state.result = None

def create_workspace(user_id, workspace_name):
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
        cursor.execute("INSERT INTO workspaces (id, workspace_name) VALUES (%s, %s) RETURNING id;", (user_id, workspace_name))
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

    return workspace_created,workspace_id


# Function to retrieve workspace history
def get_workspace_history():
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    # Retrieve workspace history
    cursor.execute("SELECT workspace_name FROM workspaces;")
    workspace_history = cursor.fetchall()
    

    print(workspace_history)

    connection.close()

    return workspace_history

def create_dynamic_table(table_name, columns, data,flattened_selected_columns):
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
    flattened_selected_columns+=["id","location"]
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

    col_dict = dict()
    for name in columns_lower,flattened_selected_columns:
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

    for idx, row in data.iterrows():
        row["id"] = idx + 1

        required_columns = ['address', 'state', 'city', 'zipcode', 'country']

        if any(col in data.columns for col in required_columns) and all(col in row.index for col in col_dict.values()):
            latitude, longitude = update_location(row)
            if latitude is not None and longitude is not None:
                row["location"] += f" ({latitude}, {longitude})"
            else:
                row["location"] += " (0, 0)"
        else:
            print("Skipping row due to missing location-related columns.")

        print("columns....", columns_lower)
        values = "', '".join(str(row[col]) for col in flattened_selected_columns if col in row.index)
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

def fetch_global_headers_from_database(workspace_name):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()
    print("workspace_name in thefetch ",workspace_name)
    query = f"SELECT global_headers FROM workspaces WHERE workspace_name= '{workspace_name}';"

    cursor.execute(query)
    result = cursor.fetchone()
    

    print("result",result)
    if result is not None:
        global_headers_str = result[0]
        global_headers_list = [header.strip() for header in global_headers_str[0:-1].split(',')]
    else:
        # Handle the case where no results are found (e.g., return an empty list)
        global_headers_list = []

    cursor.close()
    connection.close()

    return global_headers_list




def update_json_mapping_in_database(workspace_name,table_name, global_headers, selected_columns):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

   
    mapping_json = json.dumps(dict(zip(global_headers, selected_columns)))
    
    update_query = f"UPDATE workspaces SET table_name = %s WHERE workspace_name = %s;"
    
    cursor.execute(update_query,(table_name,workspace_name))
    update_query = f"UPDATE workspaces SET mapping_json = %s WHERE table_name = %s;"
    cursor.execute(update_query, (mapping_json, table_name))

    # insert_query = f"INSERT INTO workspaces (workspace_name,table_name,mapping_json) VALUES('{workspace_name}','{table_name}','{mapping_json}');"
    
    # cursor.execute(insert_query)

    connection.commit()
    cursor.close()
    connection.close()




def save_global_headers(workspace_name, global_headers_input):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    update_query = "UPDATE workspaces SET global_headers = %s WHERE workspace_name = %s;"
    cursor.execute(update_query, (global_headers_input, workspace_name))
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

    return hash(password)

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
        cursor.execute("SELECT password FROM users WHERE username = %s;", (username,))
        hashed_password = cursor.fetchone()

        cursor.close()
        connection.close()

        if hashed_password:
            print(verify_password(password, hashed_password[0]))
            if verify_password(password, hashed_password[0]):
                return True
            else:
                return False
        else:
            return False
    except Exception as e:
        print(f"Error fetching user credentials: {e}")
        return False
    
def verify_password(input_password, hashed_password):
    print(input_password,int(hashed_password),hash_password(input_password))
    print(type(hashed_password),type(hash_password(input_password)))
    int_pass=int(hashed_password)
    return hash_password(input_password) == int_pass
    
with st.sidebar:
    st.image("genpactlogo.png")
    selected = option_menu("EXPOSURE MANAGEMENT", ["SignUP","Login Page","Workspaces", "Data Upload", 'Update Data'], menu_icon="cast", default_index=0)

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
        user_data = fetch_user_credentials(username_input, password_input)
        print(user_data)
        if user_data:
            # st.title(f'Welcome *{user_data["name"]}*')
            st.write("You have successfully Logged In!")
        else:
            st.error('Username/password is incorrect')
# 'Workspaces' section
if selected == 'Workspaces':
    workspace_name = st.text_input("Enter Workspace Name")
    global_headers_input = st.text_input("Enter Global Headers (comma-separated):")
    workspace_created = st.session_state.get('workspace_created', False)


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
            user_id = 1 if latest_user_id is None else latest_user_id + 1

            workspace_created, workspace_id = create_workspace(user_id, workspace_name)

            # global_headers_input = st.text_input("Enter Global Headers (comma-separated):")
            print("function before call")
            print("workspace name ...........",workspace_name)
            print("global -----------",global_headers_input)
            save_global_headers(workspace_name, global_headers_input)
            print("executed...............")
                    

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
        workspace_history = get_workspace_history()
        formatted_workspaces = [workspace[0].strip("()").replace(",", "") for workspace in workspace_history]
        selected_workspace = st.selectbox("Select Workspace:", formatted_workspaces, key='workspace_dropdown')

        # if selected_workspace:
        #     st.write(f"You selected workspace: {selected_workspace}")

        #     if st.button('Navigate to Update Section', key='navigate_to_update_button'):
        #         st.session_state.selected_workspace = selected_workspace
        #         st.session_state.create_new_workspace = False  

        #     st.session_state.workspace_name = selected_workspace

        # else:
        #     st.info("No workspaces found.")

# Data Upload with mapping column functionality
if selected == 'Data Upload':
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])


    workspace_name=st.session_state.workspace_name
    if uploaded_file is not None:
        data = pd.read_excel(uploaded_file)
        data.columns = [col.lower().replace(' ', '_') for col in data.columns]
        st.session_state.global_headers = fetch_global_headers_from_database(workspace_name)
        global_headers = st.session_state.global_headers

        st.write("### Select Attributes")

        if global_headers:
            col1, col2 = st.columns(2)

            selected_columns = {}
            for header in global_headers:
                col1.markdown(
                    f"""<div style="width: 150px;height: 60px; margin-top: 25px;font-size: 26px;font-weight: bold;">{header}:</div>""",
                    unsafe_allow_html=True,
                )

                previously_selected_columns = []
                for prev_header, prev_selected in selected_columns.items():
                    if prev_header != header:
                        previously_selected_columns.extend(prev_selected)

                available_options = [col for col in data.columns.tolist() if col not in previously_selected_columns]

                selected_spreadsheet_header = col2.multiselect("", available_options, key=f"selectbox_{header}")

                selected_columns[header] = selected_spreadsheet_header

            if st.button('Submit', key='create_table_button') and global_headers:
                table_name = f"table{np.random.randint(100)}"
                flattened_selected_columns = [col for sublist in selected_columns.values() for col in sublist]

                create_dynamic_table(table_name, selected_columns, data, flattened_selected_columns)

                st.success(f'Submitted Successfully!')

                # Retrieve the workspace name from session state
                workspace_name = st.session_state.workspace_name

                update_json_mapping_in_database(workspace_name, table_name, global_headers, flattened_selected_columns)

                st.session_state.table_name = table_name



# Add the 'Update Data' section code here
if selected == 'Update Data':
    if not st.session_state.table_name:
        st.warning('Please create a table first in the "Data Upload" section.')
    else:
        table_data = fetch_data(st.session_state.table_name)

        if table_data.empty:
            st.warning(f'Table "{st.session_state.table_name}" not found.')
        else:
            # st.write(f"### Current Data in Table {st.session_state.table_name}")
            # st.dataframe(table_data)

            st.write("### Data")
            updated_data = st.data_editor(data=table_data)

            if st.button('Update', key='save_changes_button'):
                update_data(table_data, updated_data, st.session_state.table_name, table_data.columns)
                st.success('Updated successfully!')

                # Add a download button to download the updated dataframe
                download_button = st.download_button(
                    label="Download Updated Data",
                    data=updated_data.to_csv(index=False).encode('utf-8'),
                    file_name=f"updated_data_{st.session_state.table_name}.csv",
                    key='download_button'
                )