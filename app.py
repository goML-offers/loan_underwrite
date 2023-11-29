import streamlit as st
import pandas as pd
from io import StringIO
from synthetic import read_csv_header
from streamlit_option_menu import option_menu
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import numpy as np
import pickle as cPickle

with st.sidebar:
    selected = option_menu("LOAN UNDERWRITING", ["Data Upload", 'Synthetic Data Generation','Training','Prediction'], menu_icon="cast", default_index=0)

st.session_state.result = None
if selected == 'Data Upload':
    uploaded_file = st.file_uploader("Choose a CSV File")
    if uploaded_file is not None:
        # To read file as bytes:
        bytes_data = uploaded_file.getvalue()
        data_byte=str(bytes_data,'utf-8')
        data = StringIO(data_byte) 
        df=pd.read_csv(data)
        print(df.columns.values)
        st.session_state.result = df
        #st.dataframe(df.head())
        st.write(df)
        df.to_csv('data.csv')
        

if selected == 'Synthetic Data Generation':
    if st.button('Generate Synthetic Data'):
        df=pd.read_csv('data.csv',skipinitialspace = True)
        synth_data=read_csv_header(df)
        synth_data.to_csv('synth_data.csv')
        st.dataframe(synth_data.head())


if selected == 'Training':
    data=pd.read_csv('data.csv',skipinitialspace = True)
    synth_data=pd.read_csv('synth_data.csv',skipinitialspace = True)
    df=pd.concat([data, synth_data], ignore_index=True)
    # Define features (X) and labels (y)
    options = st.multiselect(
    'What are your attributes on which you want to train your model',
    df.columns.values,label_visibility="hidden")
    X = df[options]
    print("===========================")
    print(X.head())
    print("============================")
    y = df['loan_status']
    if st.button('Train the Data'):
        with open("features.pkl", "wb") as file:
            cPickle.dump(options, file)
        # Initialize RandomForestClassifier
        rf_classifier = RandomForestClassifier(random_state=42)

        # Define hyperparameters for GridSearchCV
        param_grid = {
            'n_estimators': [50, 100, 200],
            'max_depth': [None, 5, 10],
            'min_samples_split': [2, 5, 10]
        }

        # Perform Grid Search Cross Validation
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        grid_search = GridSearchCV(rf_classifier, param_grid, cv=5, scoring='accuracy')
        grid_search.fit(X_train, y_train)

        # Get the best estimator
        best_estimator = grid_search.best_estimator_

        # Predict labels for the test set
        y_pred = best_estimator.predict(X_test)

        # Calculate accuracy
        accuracy = accuracy_score(y_test, y_pred)
        # multiply by 10 with two decimal points
        accuracy = np.round(accuracy*100, 2)
        # Train RandomForestClassifier on the entire dataset
        rf_classifier.fit(X, y)
        
        precision = precision_score(y_test, y_pred, average='binary', pos_label='Approved')
        precision = np.round(precision*100, 2)
        recall = recall_score(y_test, y_pred, average='binary', pos_label='Approved')
        recall = np.round(recall*100, 2)

        col1, col2, col3 = st.columns(3)
        col1.metric("Model Accuracy", accuracy)
        col2.metric("Model Precision", precision)
        col3.metric("Model Recall", recall)
        with open('model.pkl', 'wb') as f:
            cPickle.dump(rf_classifier, f)

if selected == 'Prediction':
    uploaded_file = st.file_uploader("Choose Your Test Data")
    if uploaded_file is not None:
        # To read file as bytes:
        bytes_data = uploaded_file.getvalue()
        data_byte=str(bytes_data,'utf-8')
        data = StringIO(data_byte)
        df=pd.read_csv(data)
        with open('model.pkl', 'rb') as f:
            rf_classifier = cPickle.load(f)
        
        with open('features.pkl', 'rb') as f:
            f_names = cPickle.load(f)
        print("**************")
        print(f_names)
        print("**************")
        predictions  = rf_classifier.predict(df[f_names])
        df['predictions'] = predictions
        st.write(df)
        st.download_button(
        label="Download data as CSV",
        data=df.to_csv().encode('utf-8'),
        file_name='prediction.csv',
        mime='text/csv',
        )
