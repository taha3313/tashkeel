from contextlib import asynccontextmanager
from pathlib import Path
from io import BytesIO
from threading import BoundedSemaphore
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app.documents import ARABIC, MAX_FILE, MAX_TEXT, process_docx, vocalize
from app.vocalizer import TashkeelUnavailable, complete_text, get_vocalizer

STATIC = Path(__file__).resolve().parent.parent / 'static'
WORK = BoundedSemaphore(1)

@asynccontextmanager
async def lifespan(app):
    get_vocalizer()
    yield

app = FastAPI(title='Tashkeel | تشكيل', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=STATIC), name='static')

@app.middleware('http')
async def headers(request, call_next):
    if request.url.path.startswith('/api/'):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_FILE + 65536:
                return JSONResponse({'detail': 'الطلب كبير جدًا. الحد الأقصى للملف ٥ ميغابايت.'}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; font-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/')
def index():
    return FileResponse(STATIC / 'index.html')

@app.get('/health')
def health():
    return {'status': 'ok'}

class TextInput(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT)

@app.post('/api/tashkeel')
def text(request: TextInput):
    if not ARABIC.search(request.text):
        raise HTTPException(422, 'أدخل نصًا عربيًا أولًا.')
    if not WORK.acquire(blocking=False):
        raise HTTPException(429, 'الخدمة مشغولة الآن. أعد المحاولة بعد قليل.')
    try:
        return {'text': vocalize(request.text, complete_text)}
    except TashkeelUnavailable as exc:
        raise HTTPException(503, 'تعذّر تشكيل النص. أعد المحاولة بعد قليل.') from exc
    finally:
        WORK.release()

@app.post('/api/document')
def document(file: UploadFile = File(...)):
    if not (file.filename or '').lower().endswith('.docx'):
        raise HTTPException(422, 'نقبل ملفات .docx فقط. احفظ ملف .doc القديم بصيغة .docx أولًا.')
    if not WORK.acquire(blocking=False):
        raise HTTPException(429, 'الخدمة مشغولة الآن. أعد المحاولة بعد قليل.')
    try:
        data = file.file.read(MAX_FILE + 1)
        result = process_docx(data, complete_text)
        return StreamingResponse(BytesIO(result), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                                 headers={'Content-Disposition': 'attachment; filename="tashkeel.docx"'})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except TashkeelUnavailable as exc:
        raise HTTPException(503, 'تعذّر تشكيل المستند. أعد المحاولة بعد قليل.') from exc
    finally:
        file.file.close()
        WORK.release()
