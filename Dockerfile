FROM python:3.12

ENV PYTHONUNBUFFERED True

COPY ./ /ChatGPT-Line-Bot
WORKDIR /ChatGPT-Line-Bot
RUN find . -name "*.ipynb" -exec rm {} +
RUN apt-get install libpq-dev
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

# 使用新的統一入口點
CMD ["gunicorn", "-c", "gunicorn.conf.py", "main:application"]