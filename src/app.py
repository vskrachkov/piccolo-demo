from fastapi import FastAPI
from piccolo.engine import engine_finder
from piccolo_admin.endpoints import create_admin
from starlette.routing import Mount

from blog.piccolo_app import APP_CONFIG

app = FastAPI(
    routes=[
        Mount(
            "/admin/",
            create_admin(
                tables=APP_CONFIG.table_classes,
                site_name="Blog Admin",
                # Required when running under HTTPS:
                # allowed_hosts=['my_site.com']
            ),
        ),
    ],
)


@app.on_event("startup")
async def open_database_connection_pool():
    engine = engine_finder()
    await engine.start_connection_pool()


@app.on_event("shutdown")
async def close_database_connection_pool():
    engine = engine_finder()
    await engine.close_connection_pool()
