# AI ATS Recruitment MVP

Ung dung Django cho he thong tuyen dung AI ATS theo tai lieu `ATS_REQUIREMENTS.md`.

## Cach chay local

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Mo trinh duyet tai `http://127.0.0.1:8000/`.

## Tai khoan demo

- Admin: `admin` / `admin12345`
- Recruiter: `recruiter_demo` / `demo12345`
- Candidate: `candidate_demo` / `demo12345`

## Cau hinh email Gmail SMTP

Tao file `.env` tu `.env.example`, sau do dien:

```env
EMAIL_HOST_USER=your-gmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
DEFAULT_FROM_EMAIL=your-gmail@gmail.com
```

Can dung Gmail App Password, khong dung mat khau Gmail chinh.

## Ghi chu ATS

- MVP chi nhan CV PDF co text that, chua ho tro OCR file scan.
- File CV luu trong `media/`, database chi luu duong dan va metadata.
- Semantic matching dung multilingual MiniLM model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` qua HuggingFace `transformers`.
- Neu model semantic chua san sang, service se fallback sang keyword similarity de khong lam hong flow ung tuyen.
- Tinh lai CV parsing va ATS breakdown cho du lieu cu:

```powershell
python manage.py reprocess_ats
```
