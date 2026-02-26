from  fastapi import APIRouter, Depends, status, Header
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from shared.depends import UserServiceDep


user_route = APIRouter(prefix="/api/v1/users")


@user_route.get("/me")
async def get_me(service : UserServiceDep, user_id = Header(..., alias="X-User-Id")):
    user = await service.get_me(user_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "detail" : "Ok", 
            "data" : {
                "user" : user
                }
            }
    )

