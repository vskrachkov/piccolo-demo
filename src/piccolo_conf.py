from environs import Env
from piccolo.engine.postgres import PostgresEngine

from piccolo.conf.apps import AppRegistry

env = Env()
env.read_env()  # read .env file, if it exists


DB = PostgresEngine(
    config={
        "database": env.str("DB_NAME"),
        "user": env.str("DB_USER"),
        "password": env.str("DB_PASSWORD"),
        "host": env.str("DB_HOST"),
        "port": env.int("DB_PORT"),
    }
)

APP_REGISTRY = AppRegistry(
    apps=["blog.piccolo_app", "piccolo_admin.piccolo_app"]
)
