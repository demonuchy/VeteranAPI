from typing import List, Optional
from fastapi import APIRouter, Form, File, UploadFile, Header, status
from fastapi.responses import JSONResponse


from shared.depends import NewsServiceDep


news_route = APIRouter(prefix="/api/v1/news")


@news_route.get("/private")
async def private():
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )


@news_route.post("/")
async def create_news( 
    service: NewsServiceDep,
    title: str = Form(..., min_length=3, max_length=200),
    body: str = Form(..., min_length=10),
    images: List[UploadFile] = File(default=[]),
    user_id: int = Header(..., alias="X-User-Id")
    ):
    await service.create_news(user_id=user_id, title=title, body=body, upload_images=images)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED, 
        content={"detail" : "News created"}
        )


@news_route.get("/")
async def get_news_all(service : NewsServiceDep):
    news = await service.get_all_news()
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "detail" : "Ok", 
            "data" : {
                "news" : news
                }
            }
        )


@news_route.get("/{news_id}")
async def get_news(service : NewsServiceDep, news_id : int):
    news = await service.get_news(news_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "detail" : "Ok", 
            "data" : {
                "news" : news
                }
            }
        )


@news_route.delete("/{news_id}")
async def delete_news(service : NewsServiceDep, news_id : int):
    await service.delete_news(news_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={
            "detail" : "Ok", 
            }
        )


@news_route.patch("/{news_id}")
async def update_news(
    service : NewsServiceDep, 
    news_id : int,
    title: Optional[str] = Form(None),
    body: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(default=[]),
    ):
    await service.update_news(
        news_id=int(news_id), 
        title=title, 
        body=body, 
        upload_images=images
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )


@news_route.post("/{news_id}/comment")
async def leave_comment(
    service : NewsServiceDep, 
    content : str,
    news_id : int, 
    user_id : int = Header(..., alias="X-User-Id"),
    ):
    await service.leave_comment(user_id=int(user_id), news_id=int(news_id), content=content)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )


@news_route.delete("/{news_id}/comment/{comment_id}")
async def delete_comment(
    service : NewsServiceDep,
    comment_id : int,
    news_id : int,
    user_id : int = Header(..., alias="X-User-Id"),
    ):
    await service.delete_comment(user_id=int(user_id), comment_id=comment_id)
    return JSONResponse(
        status_code=status.HTTP_200_OK, 
        content={"detail" : "Ok"}
        )