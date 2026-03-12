from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import schools
from routers import teachers
from routers import students
from routers import classes
from routers import assessments
from routers import ocr
from routers import dashboard

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://calia-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(schools.router)
app.include_router(teachers.router)
app.include_router(students.router)
app.include_router(classes.router)
app.include_router(assessments.router)
app.include_router(ocr.router)
app.include_router(dashboard.router)


@app.get("/")
def root():
    return {"status": "CALIA Backend Online"}

@app.get("/me")
def get_me(user=Depends(get_current_user)):
    return user
