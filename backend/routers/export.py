from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session
from database import get_db
from services.export_service import generate_csv, generate_excel, generate_pdf

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/csv")
def export_csv(month: str, db: Session = Depends(get_db)):
    try:
        content = generate_csv(db, month)
        return Response(
            content=content.encode("utf-8-sig"),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=shift_{month}.csv"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/excel")
def export_excel(month: str, db: Session = Depends(get_db)):
    try:
        content = generate_excel(db, month)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename=shift_{month}.xlsx"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/pdf")
def export_pdf(month: str, db: Session = Depends(get_db)):
    try:
        content = generate_pdf(db, month)
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=shift_{month}.pdf"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
