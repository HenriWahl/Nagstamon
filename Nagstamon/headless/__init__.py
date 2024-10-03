import os
import secrets
import sys
import uvicorn
from typing import Annotated
from fastapi import Depends, FastAPI, APIRouter, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials


from Nagstamon.Config import (conf)
from Nagstamon.Servers import (servers)


class HeadlessMode:
    security = HTTPBasic()
    ENVVAR_NAME_BASICAUTH_USER = 'NAGSTAMON_HEADLESS_BASICAUTH_USER'
    ENVVAR_NAME_BASICAUTH_PASSWORD = 'NAGSTAMON_HEADLESS_BASICAUTH_PASSWORD'

    """
        initialize headless rest api server
    """
    def __init__(self, argv=None):

        if not (self.ENVVAR_NAME_BASICAUTH_USER in os.environ and self.ENVVAR_NAME_BASICAUTH_PASSWORD in os.environ):
            print(f"For headless mode the following envvars must be set for basic auth: {self.ENVVAR_NAME_BASICAUTH_USER}, {self.ENVVAR_NAME_BASICAUTH_PASSWORD}")
            sys.exit(1)
        else:
            conf.headless_basicauth_user = os.environ[self.ENVVAR_NAME_BASICAUTH_USER]
            conf.headless_basicauth_password = os.environ[self.ENVVAR_NAME_BASICAUTH_PASSWORD]

        self.check_servers()

        self.api = FastAPI()

        self.router = APIRouter()
        self.router.add_api_route("/hosts", self.get_hosts, methods=["GET"], dependencies=[Depends(self.check_user)])
        self.api.include_router(self.router)

        uvicorn.run(self.api, host=conf.headless_addr, port=conf.headless_port)

    def check_user(self, credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
        current_username_bytes = credentials.username.encode("utf8")
        correct_username_bytes = str.encode(conf.headless_basicauth_user, "utf-8")
        is_correct_username = secrets.compare_digest(
            current_username_bytes, correct_username_bytes
        )
        current_password_bytes = credentials.password.encode("utf8")
        correct_password_bytes = str.encode(conf.headless_basicauth_password, "utf-8")
        is_correct_password = secrets.compare_digest(
            current_password_bytes, correct_password_bytes
        )
        if not (is_correct_username and is_correct_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Basic"},
            )
        return credentials.username

    def check_servers(self):
        """
            check if there are any servers configured and enabled
        """
        # no server is configured
        if len(servers) == 0:
            print('no_server')
            sys.exit(1)
        # no server is enabled
        elif len([x for x in conf.servers.values() if x.enabled is True]) == 0:
            print('no_server_enabled')
            sys.exit(1)

    # TODOs
    # * add caching
    # * don't authenticate on each request
    def get_hosts(self):
        all_hosts = []
        for server in servers.values():
            if server.enabled:
                server.init_config()
                status = server.GetStatus()
                all_hosts.append(server.hosts)

        return all_hosts


APP = HeadlessMode(sys.argv)
