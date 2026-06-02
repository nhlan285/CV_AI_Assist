# AI ATS Recruitment MVP

Ung dung Django cho he thong tuyen dung AI ATS theo tai lieu `ATS_REQUIREMENTS.md`.
Du an hien dung SQLite, Django template, Chart.js, HuggingFace MiniLM, spaCy va Django Channels.

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

## Tinh nang da hoan thanh

- Phan quyen candidate/recruiter bang Django auth.
- Recruiter dang ky kem tao cong ty ngay khi dang ky.
- Candidate upload CV PDF, file luu trong `media/`, database luu duong dan va metadata.
- CV parser doc text PDF bang PyMuPDF, dung spaCy PhraseMatcher de nhan dien skill theo section/evidence.
- Parser tach section CV: skills, experience, education, projects, certifications.
- ATS scoring ket hop semantic score, skill score, experience, education va domain signal.
- Semantic matching dung multilingual MiniLM qua HuggingFace `transformers`.
- Skill dictionary/alias quan tri duoc trong Django Admin bang model `Skill` va `SkillAlias`.
- Skill evidence duoc luu vao CV va ATS breakdown de recruiter xem ly do match.
- Recruiter dashboard co metric card va Chart.js: timeline CV, ATS trung binh, status, score bucket, top job.
- Man danh sach ung vien theo job co filter keyword, status, review status va ATS group.
- Recruiter job list co search, status filter va sort moi nhat/cu nhat.
- Public/candidate job list co search, filter khu vuc/skill/work mode/job type va sort.
- Notification realtime bang Django Channels + Daphne, mac dinh InMemory channel layer.
- Candidate nhan notification va email khi apply/cap nhat trang thai.
- Recruiter nhan notification gom nhom theo tung job khi co don ung tuyen moi.
- Chuong notification tren navbar, badge so chua doc, dropdown va trang `/notifications/`.
- Candidate co the soft-delete CV; CV da xoa khong dung cho apply moi nhung application cu van xem duoc.
- Test suite hien co bao phu ATS utilities, job search/sort, notification va soft-delete CV.

## Ghi chu ATS

- MVP chi nhan CV PDF co text that, chua ho tro OCR file scan.
- File CV luu trong `media/`, database chi luu duong dan va metadata.
- Danh muc skill/alias co the quan tri trong Django Admin. Seed danh muc mac dinh bang `python manage.py seed_skills`.
- spaCy dung `spacy.blank("xx")` va `PhraseMatcher`, khong can tai model ngon ngu lon trong MVP.
- Semantic matching dung multilingual MiniLM model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` qua HuggingFace `transformers`.
- Neu model semantic chua san sang, service se fallback sang keyword similarity de khong lam hong flow ung tuyen.
- Tinh lai CV parsing va ATS breakdown cho du lieu cu:

```powershell
python manage.py reprocess_ats
```

## Cau truc chinh

- `ats_site/`: cau hinh Django, ASGI/WSGI, static/media.
- `recruitment/models.py`: profile, company, job, CV, application, notification, skill dictionary.
- `recruitment/services/ats.py`: doc CV, parse CV, match skill, tinh ATS score.
- `recruitment/services/notifications.py`: tao va push notification realtime.
- `recruitment/templates/`: giao dien candidate/recruiter/admin-facing pages.
- `static/recruitment/app.css`: style tong the dashboard, list, filter, notification.
