
FROM python:3.9

COPY requirements.txt app/requirements.txt

WORKDIR /app

RUN git clone https://github.com/streamlit/streamlit-example.git .
RUN pip install -r requirements.txt

COPY . /app

EXPOSE 8501

CMD ["streamlit","run","ui.py","--server.port=8501", "--server.address=0.0.0.0"]