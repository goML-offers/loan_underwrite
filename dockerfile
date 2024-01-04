
FROM python:3.9

COPY requirements.txt app/requirements.txt

WORKDIR /app

RUN echo "#!/bin/sh\nexit 0" > /usr/local/bin/sudo && chmod +x /usr/local/bin/sudo

RUN pip install -r requirements.txt

COPY . /app

EXPOSE 8501

CMD ["streamlit","run","ui.py","--server.port=8501", "--server.address=0.0.0.0"]