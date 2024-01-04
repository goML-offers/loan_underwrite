import streamlit as st
import pandas as pd
import numpy as np
import psycopg2
from opencage.geocoder import OpenCageGeocode
from streamlit_option_menu import option_menu

opencage_api_key = "25d4749b39114fdb9898642ddb1db305"
geolocator = OpenCageGeocode(opencage_api_key)


if "table_name" not in st.session_state:
    st.session_state.table_name = ""

if "result" not in st.session_state:
    st.session_state.result = None

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

def update_data(original_data, updated_data, table_name,columns):
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
            update_location_in_db(cursor, row, table_name,columns)

    connection.commit()
    connection.close()

def update_location_in_db(cursor, row, table_name,columns):
   

    col_dict=dict()
    for name in columns:
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
    # latitude, longitude = update_location(
    #     row[col_dict['address']], row[col_dict['city']], row[col_dict['state']], row[col_dict['zipcode']], row[col_dict['country']]
    # )
    latitude,longitude=update_location(row)
    print(latitude,longitude)
    if latitude is not None and longitude is not None:
        # Construct the new location value with latitude and longitude
        new_location_value = f"({latitude}, {longitude})"
        
        # Update the specified address-related columns and location in the database
        update_columns = [f"{col} = '{row[col]}'" for col in columns if col in row.index and col != 'location']
        update_columns.append(f"location = '{new_location_value}'")

        update_columns_str = ', '.join(update_columns)

        query = f"UPDATE {table_name} SET {update_columns_str} WHERE id = '{row['id']}';"
        print("Update Query:", query)
        cursor.execute(query)



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


# Creating a Workspace
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

    # Check if the workspace already exists for the user
    cursor.execute("SELECT id FROM workspaces WHERE user_id = %s AND workspace_name = %s;", (user_id, workspace_name))
    existing_workspace = cursor.fetchone()

    if existing_workspace:
        st.warning(f'Workspace "{workspace_name}" already exists for user {user_id}.')
        return existing_workspace[0]  # Return the existing workspace_id

    # Create a new workspace entry
    cursor.execute("INSERT INTO workspaces (user_id, workspace_name) VALUES (%s, %s) RETURNING id;", (user_id, workspace_name))
    workspace_id = cursor.fetchone()[0]

    connection.commit()
    connection.close()

    return workspace_id

def create_table(workspace_id, table_name, columns):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    # Check if the table already exists in the workspace
    cursor.execute("SELECT id FROM tables WHERE workspace_id = %s AND table_name = %s;", (workspace_id, table_name))
    existing_table = cursor.fetchone()

    if existing_table:
        st.warning(f'Table "{table_name}" already exists in workspace {workspace_id}.')
        return existing_table[0]  # Return the existing table_id

    # Create a new table entry
    cursor.execute("INSERT INTO tables (workspace_id, table_name, columns) VALUES (%s, %s, %s) RETURNING id;",
                   (workspace_id, table_name, json.dumps(columns)))
    table_id = cursor.fetchone()[0]

    connection.commit()
    connection.close()

    return table_id

def create_workspace_table(workspace_id, table_name, array_data, json_file):
    connection_params = {
        'host': 'database-1.cmeaoe1g4zcd.ap-south-1.rds.amazonaws.com',
        'port': '5432',
        'database': 'postgres',
        'user': 'postgres',
        'password': 'postgres'
    }

    connection = psycopg2.connect(**connection_params)
    cursor = connection.cursor()

    # Check if the table already exists in the workspace
    cursor.execute("SELECT id FROM tables WHERE workspace_id = %s AND table_name = %s;", (workspace_id, table_name))
    existing_table = cursor.fetchone()

    if existing_table:
        st.warning(f'Table "{table_name}" already exists in workspace {workspace_id}.')
        return existing_table[0]  # Return the existing table_id

    # Create a new table entry
    cursor.execute("INSERT INTO tables (workspace_id, table_name, array_data, json_file) VALUES (%s, %s, %s, %s) RETURNING id;",
                   (workspace_id, table_name, json.dumps(array_data), json.dumps(json_file)))
    table_id = cursor.fetchone()[0]

    connection.commit()
    connection.close()

    return table_id



with st.sidebar:
    st.image("genpactlogo.png")
    selected = option_menu("EXPOSURE MANAGEMENT", ["Workspaces","Data Upload", 'Update Data'], menu_icon="cast", default_index=0)

st.session_state.result = None


if selected == 'Workspaces':

    user_id = 1  
    workspace_name = st.text_input("Enter Workspace Name")
    table_name = st.text_input("Enter Table Name")
    selected_columns = st.multiselect("Columns", ["column1", "column2", "column3"])  # Replace with your actual column selection mechanism
    array_data = [1, 2, 3]  # Replace with your actual array data
    json_file = {"key": "value"}  # Replace with your actual JSON file data

    # Create a new workspace
    workspace_id = create_workspace(user_id, workspace_name)

    # Create a new table in the workspace
    table_id = create_table(workspace_id, table_name, selected_columns)

    # Create a new workspace table entry
    workspace_table_id = create_workspace_table(workspace_id, table_name, array_data, json_file)

    # Provide feedback to the user
    st.success(f'Workspace "{workspace_name}" created successfully with table "{table_name}".')
if selected == 'Data Upload':
    uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx", "xls"])

    if uploaded_file is not None:
        data = pd.read_excel(uploaded_file)

        data.columns = [col.lower().replace(' ', '_') for col in data.columns]
        # updated_data = st.data_editor(data)
        st.write("### Select Attributes")
        selected_columns = st.multiselect("Columns", data.columns.tolist())

        if st.button('Submit', key='create_table_button') and selected_columns:
            table_name = f"table{np.random.randint(100)}"
            create_dynamic_table(table_name, selected_columns, data)
            st.success(f'Submitted Successfully!')
            st.session_state.table_name = table_name

        
        


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
                update_data(table_data, updated_data, st.session_state.table_name,table_data.columns)
                st.success('Updated successfully!')
