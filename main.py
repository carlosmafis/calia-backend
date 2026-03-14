from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import schools
from routers import classes
from routers import students
from routers import assessments
from routers import ocr
from core.auth import get_current_user
from fastapi import Depends

@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://calia-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schools.router, prefix="/schools")
app.include_router(classes.router, prefix="/classes")
app.include_router(students.router, prefix="/students")
app.include_router(assessments.router, prefix="/assessments")
app.include_router(ocr.router, prefix="/ocr")

@app.get("/")
def root():
    return {"status":"CALIA backend online"}