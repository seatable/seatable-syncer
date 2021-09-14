import logging

logging.basicConfig(
    filename='sync_server.log',
    filemode='a',
    format="[%(asctime)s] [%(levelname)s] %(name)s:%(lineno)s %(funcName)s %(message)s",
    level=logging.INFO
)

from app import app


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5066)
