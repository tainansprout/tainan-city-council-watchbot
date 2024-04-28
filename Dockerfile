FROM python:3.12

COPY ./ /ChatGPT-Line-Bot
WORKDIR /ChatGPT-Line-Bot
RUN apt-get install libpq-dev
RUN pip3 install -r requirements.txt

CMD ["python3", "main.py"]