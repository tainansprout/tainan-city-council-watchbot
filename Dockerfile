FROM python:3.12

ENV PYTHONUNBUFFERED True

COPY ./ /ChatGPT-Line-Bot
WORKDIR /ChatGPT-Line-Bot
RUN find . -name "*.ipynb" -exec rm {} +
RUN apt-get install libpq-dev
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt

# 使用 WSGI 入口點和配置文件
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:application"]