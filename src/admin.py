import inspect
import json
import os
import typing as t

import piccolo_admin
from fastapi import FastAPI
from piccolo.table import Table
from piccolo_admin.endpoints import (
    ASSET_PATH,
    FormConfig,
    MetaResponseModel,
    FormConfigResponseModel,
    UserResponseModel,
    TableConfig,
)
from piccolo_api.crud.endpoints import PiccoloCRUD
from piccolo_api.fastapi.endpoints import FastAPIWrapper, FastAPIKwargs
from piccolo_api.openapi.endpoints import swagger_ui
from pydantic import ValidationError
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.staticfiles import StaticFiles


class AdminPanelRouter(FastAPI):
    def __init__(
        self,
        tables: t.List[TableConfig] | t.List[t.Type[Table]],
        site_name: str = "Site Name",
        forms: t.Iterable[FormConfig] = (),
    ) -> None:
        super().__init__()

        self.site_name = site_name
        self.table_configs = self.provide_table_config(tables)
        self.forms = forms
        self.form_config_map = {form.slug: form for form in self.forms}

        self.configure_admin_ui()
        self.configure_admin_api()

    def configure_admin_api(self):
        api_app = self.provide_api_app(self.table_configs)
        self.mount(path="/api", app=self.auth_middleware(api_app))
        self.add_api_route("/meta/", endpoint=self.get_meta)  # type: ignore

    def configure_admin_ui(self):
        self.router.add_route(path="/", endpoint=self.get_root, methods=["GET"])
        with open(os.path.join(ASSET_PATH, "index.html")) as f:
            self.template = f.read()
        self.mount(
            path="/css",
            app=StaticFiles(directory=os.path.join(ASSET_PATH, "css")),
        )
        self.mount(
            path="/js",
            app=StaticFiles(directory=os.path.join(ASSET_PATH, "js")),
        )

    def auth_middleware(self, app):
        # auth_app = FastAPI()
        # if not rate_limit_provider:
        #     rate_limit_provider = InMemoryLimitProvider(
        #         limit=1000, timespan=300
        #     )
        # auth_app.mount(
        #     path="/login/",
        #     app=RateLimitingMiddleware(
        #         app=session_login(
        #             auth_table=self.auth_table,
        #             session_table=session_table,
        #             session_expiry=session_expiry,
        #             max_session_expiry=max_session_expiry,
        #             redirect_to=None,
        #             production=production,
        #         ),
        #         provider=rate_limit_provider,
        #     ),
        # )
        # auth_app.add_route(
        #     path="/logout/",
        #     route=session_logout(session_table=session_table),
        #     methods=["POST"],
        # )
        # self.mount(path="/auth", app=auth_app)
        # auth_middleware = partial(
        #     AuthenticationMiddleware,
        #     backend=SessionsAuthBackend(
        #         auth_table=auth_table,
        #         session_table=session_table,
        #         admin_only=True,
        #         increase_expiry=increase_expiry,
        #     ),
        #     on_error=handle_auth_exception,
        # )
        # auth_middleware(app)
        return app

    def provide_api_app(
        self,
        table_configs: t.List[TableConfig],
        read_only: bool = False,
        page_size: int = 25,
    ):
        api_app = FastAPI(docs_url=None)
        api_app.mount("/docs/", swagger_ui(schema_url="../openapi.json"))
        for table_config in table_configs:
            table_class = table_config.table_class
            visible_column_names = table_config.get_visible_column_names()
            visible_filter_names = table_config.get_visible_filter_names()
            FastAPIWrapper(
                root_url=f"/tables/{table_class._meta.tablename}/",
                fastapi_app=api_app,
                piccolo_crud=PiccoloCRUD(
                    table=table_class,
                    read_only=read_only,
                    page_size=page_size,
                    schema_extra={
                        "visible_column_names": visible_column_names,
                        "visible_filter_names": visible_filter_names,
                    },
                ),
                fastapi_kwargs=FastAPIKwargs(
                    all_routes={
                        "tags": [f"{table_class._meta.tablename.capitalize()}"]
                    },
                ),
            )
        api_app.add_api_route(
            path="/tables/",
            endpoint=self.get_table_list,  # type: ignore
            methods=["GET"],
            response_model=t.List[str],
            tags=["Tables"],
        )
        api_app.add_api_route(
            path="/meta/",
            endpoint=self.get_meta,  # type: ignore
            methods=["GET"],
            tags=["Meta"],
            response_model=MetaResponseModel,
        )
        api_app.add_api_route(
            path="/forms/",
            endpoint=self.get_forms,  # type: ignore
            methods=["GET"],
            tags=["Forms"],
            response_model=t.List[FormConfigResponseModel],
        )
        api_app.add_api_route(
            path="/forms/{form_slug:str}/",
            endpoint=self.get_single_form,  # type: ignore
            methods=["GET"],
            tags=["Forms"],
        )
        api_app.add_api_route(
            path="/forms/{form_slug:str}/schema/",
            endpoint=self.get_single_form_schema,  # type: ignore
            methods=["GET"],
            tags=["Forms"],
        )
        api_app.add_api_route(
            path="/forms/{form_slug:str}/",
            endpoint=self.post_single_form,  # type: ignore
            methods=["POST"],
            tags=["Forms"],
        )
        api_app.add_api_route(
            path="/user/",
            endpoint=self.get_user,  # type: ignore
            methods=["GET"],
            tags=["User"],
            response_model=UserResponseModel,
        )
        return api_app

    def provide_table_config(self, tables: t.List[TableConfig] | t.List[t.Type[Table]]):
        table_configs: t.List[TableConfig] = []
        for table in tables:
            if isinstance(table, TableConfig):
                table_configs.append(table)
            else:
                table_configs.append(TableConfig(table_class=table))
        return table_configs

    async def get_root(self, request: Request) -> HTMLResponse:
        return HTMLResponse(self.template)

    def get_user(self, request: Request) -> UserResponseModel:
        return UserResponseModel(
            username=request.user.display_name,
            user_id=request.user.user_id,
        )

    def get_forms(self) -> t.List[FormConfigResponseModel]:
        """
        Returns a list of all forms registered with the admin.
        """
        return [
            FormConfigResponseModel(
                name=form.name, slug=form.slug, description=form.description
            )
            for form in self.forms
        ]

    def get_single_form(self, form_slug: str) -> FormConfigResponseModel:
        """
        Returns the FormConfig for the given form.
        """
        form = self.form_config_map.get(form_slug, None)
        if form is None:
            raise HTTPException(status_code=404, detail="No such form found")
        else:
            return FormConfigResponseModel(
                name=form.name,
                slug=form.slug,
                description=form.description,
            )

    def get_single_form_schema(self, form_slug: str) -> t.Dict[str, t.Any]:
        form_config = self.form_config_map.get(form_slug)

        if form_config is None:
            raise HTTPException(status_code=404, detail="No such form found")
        else:
            return form_config.pydantic_model.schema()

    async def post_single_form(
        self, request: Request, form_slug: str
    ) -> JSONResponse:
        form_config = self.form_config_map.get(form_slug)
        data = await request.json()

        if form_config is None:
            raise HTTPException(status_code=404, detail="No such form found")

        try:
            model_instance = form_config.pydantic_model(**data)
        except ValidationError as exception:
            return JSONResponse(
                {"message": json.loads(exception.json())}, status_code=400
            )

        try:
            endpoint = form_config.endpoint
            if inspect.iscoroutinefunction(endpoint):
                response = await endpoint(  # type: ignore
                    request, model_instance
                )
            else:
                response = endpoint(request, model_instance)
        except ValueError as exception:
            return JSONResponse({"message": str(exception)}, status_code=400)

        message = (
            response if isinstance(response, str) else "Successfully submitted"
        )
        return JSONResponse({"message": message})

    def get_meta(self) -> MetaResponseModel:
        return MetaResponseModel(
            piccolo_admin_version=piccolo_admin.version.__VERSION__,
            site_name=self.site_name,
        )

    def get_table_list(self) -> t.List[str]:
        """
        Returns a list of all tables registered with the admin.
        """
        return [i.table_class._meta.tablename for i in self.table_configs]
