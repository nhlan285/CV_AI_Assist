# ATS Recruitment System Requirements

## 1. Trang thai tai lieu

- Nguon ban dau: `ATS_Recruitment_System_Specification.docx`
- Muc dich: Tong hop yeu cau he thong da co trong file doc, ghi lai cac quyet dinh/chinh sua sau khi trao doi, va lam can cu de xay dung code.
- Trang thai: Dang lam ro yeu cau truoc khi code.

## 2. Mo ta tong quan da xac nhan tu file doc

He thong la mot nen tang tuyen dung truc tuyen co tich hop AI ATS, tuong tu VietnamWorks, TopCV va ITviec. He thong ho tro ung vien tao ho so/CV, upload CV, apply viec lam; nha tuyen dung tao cong ty, dang bai tuyen dung, quan ly ung vien va loc CV tu dong bang AI.

## 3. Cong nghe duoc de xuat trong file doc

- Backend: Django + Django REST Framework
- Database: SQLite
- NLP: spaCy + sentence-transformers
- Search Engine: Elasticsearch
- Task Queue: Celery
- Frontend: Django Templates
- Storage: AWS S3 hoac Local Storage

## 4. Chuc nang Candidate da co trong file doc

- Dang ky / dang nhap
- Quan ly ho so ca nhan
- Upload CV PDF/DOCX
- Tao CV online
- Apply cong viec
- Luu viec lam yeu thich
- Nhan goi y cong viec bang AI
- Theo doi trang thai ung tuyen
- Chat voi recruiter
- Nhan thong bao email

## 5. Chuc nang Recruiter da co trong file doc

- Dang ky tai khoan recruiter
- Tao cong ty
- Dang bai tuyen dung
- Quan ly danh sach ung vien
- Loc CV tu dong bang AI
- Xem ATS score
- Tim kiem ung vien
- Danh dau ung vien tiem nang
- Gui email phong van

## 6. Chuc nang AI ATS da co trong file doc

- CV parsing bang spaCy
- Skill extraction
- Email extraction
- Phone extraction
- Experience extraction
- Education extraction
- Keyword matching
- Semantic matching
- ATS scoring
- Phat hien ky nang con thieu
- AI goi y cai thien CV

## 7. Database schema muc cao tu file doc

- User
- CandidateProfile
- RecruiterProfile
- Company
- JobPost
- Application
- Skill
- Education
- Experience
- Notification
- Message

## 8. Quy trinh hoat dong da co trong file doc

1. Ung vien upload CV.
2. He thong extract text tu PDF/DOCX.
3. spaCy xu ly NLP.
4. Luu du lieu co cau truc vao database.
5. AI matching voi Job Description.
6. Tinh ATS score.
7. Recruiter xem ranking ung vien.

## 9. CV Builder da co trong file doc

- Keo tha sections
- Nhieu template
- Export PDF
- Realtime preview
- Tuy chinh mau sac
- Auto save

## 10. Tim kiem da co trong file doc

- Search jobs
- Search candidates
- Autocomplete
- Filter theo skill
- Filter theo location
- Ranking theo relevance

## 11. Dashboard Analytics da co trong file doc

- So luong CV apply
- Conversion rate
- Luot xem bai tuyen dung
- Top ky nang pho bien
- Thong ke tuyen dung

## 12. Security da co trong file doc

- JWT Authentication
- Role-based permissions
- Rate limiting
- CSRF protection
- File validation
- Password hashing

## 13. Roadmap ban dau tu file doc

- Phase 1: MVP
- Phase 2: AI scoring
- Phase 3: Payment + Premium
- Phase 4: Recommendation system
- Phase 5: Microservices

## 14. Cac diem can lam ro truoc khi code

- Pham vi MVP can lam ngay.
- Loai ung dung: server-rendered Django Templates hay co API DRF day du de sau nay tach frontend.
- Database dung cho do an/local demo hay gan production.
- Co che dang nhap: session auth, JWT, hay ket hop.
- Field chi tiet cho cac model.
- Cong thuc ATS score ban dau.
- Xu ly upload CV, gioi han file, loai file, va cach extract text.
- Chuc nang nao de sau MVP.
- Giao dien can co nhung man hinh nao.
- Yeu cau ve admin, seed data, test, va cach chay project.

## 15. Quyet dinh sau khi trao doi

- Q1: Chon huong MVP day du hon.
  - Bao gom: dang ky/dang nhap, phan quyen Candidate/Recruiter, recruiter dang job, candidate upload CV va apply, recruiter xem danh sach ung vien, ATS score.
  - Bo sung trong MVP: search/filter job, luu job yeu thich, trang thai ung tuyen, email thong bao, dashboard co ban.
- Q2: Chon Django session auth cho MVP.
  - Dang nhap/dang xuat dung co che mac dinh cua Django.
  - Phu hop voi frontend Django Templates.
  - Chua uu tien JWT trong MVP.
- Q3: Chon SQLite cho giai doan dau.
  - Phu hop voi demo/MVP local.
  - Can thiet ke model sach de co the chuyen sang PostgreSQL sau neu can.
  - De xuat luu file CV trong local storage qua Django `FileField`, nam trong thu muc `media/`.
  - Database chi luu metadata va duong dan file, khong luu binary CV truc tiep vao SQLite.
  - Khi can production/mo rong, co the doi storage backend sang AWS S3 hoac dich vu object storage tuong duong.
- Q4: Chon local storage trong `media/` de luu CV.
  - File CV duoc luu trong thu muc `media/`.
  - Database luu duong dan file de truy xuat.
  - Dung Django `FileField` cho file upload.
  - MVP chua dung AWS S3.
- Q5: Chon semantic matching cho ATS score MVP.
  - Dung `sentence-transformers` de tao embedding cho noi dung CV va Job Description.
  - Tinh do tuong dong ngu nghia giua CV va JD de tao ATS score.
  - Co the van extract skill/keyword de hien thi ly do match/missing skills, nhung diem chinh dua tren semantic similarity.
  - Cach nay thong minh hon keyword matching, nhung can chon model phu hop ngon ngu CV/JD va can them dependency ML.
- Q6: He thong can ho tro ca tieng Viet va tieng Anh.
  - CV va Job Description co the la tieng Viet, tieng Anh, hoac tron ca hai.
  - Semantic matching se dung multilingual model.
  - De xuat model MVP: `paraphrase-multilingual-MiniLM-L12-v2` vi ho tro da ngon ngu va tuong doi nhe.
- Q7: MVP chi ho tro upload va extract CV dang PDF.
  - Khong ho tro DOCX trong MVP.
  - Khong xu ly OCR cho CV scan anh trong MVP.
  - Chi extract text tu file PDF co noi dung text that.
  - De xuat thu vien extract PDF: `PyMuPDF`.
- Q8: UI su dung tieng Viet cho trang thai ung tuyen va cac text chinh.
  - Trang thai hien thi tren UI:
    - Da ung tuyen
    - Dang xem xet
    - Da xem
    - Phu hop
    - Phong van
    - Tu choi
    - Da tuyen
  - Trong code/database nen dung enum key tieng Anh de xu ly logic on dinh:
    - `applied`
    - `screening`
    - `reviewed`
    - `shortlisted`
    - `interview`
    - `rejected`
    - `hired`
- Q9: Chon gui email that qua SMTP Gmail.
  - MVP se cau hinh Django email backend de gui qua Gmail SMTP.
  - Can dung Gmail App Password, khong dung mat khau Gmail chinh.
  - Email credential phai luu qua bien moi truong hoac file `.env`, khong hard-code trong source code.
  - Cac su kien gui email MVP:
    - Candidate apply job thanh cong.
    - Recruiter cap nhat trang thai ung tuyen.
- Q10: Chon cau hinh Gmail SMTP bang file `.env`.
  - Project se doc cac bien email tu `.env`.
  - Tao `.env.example` de mo ta cac bien can cau hinh.
  - Khong commit `.env` that neu co chua credential.
  - Cac bien du kien:
    - `EMAIL_HOST_USER`
    - `EMAIL_HOST_PASSWORD`
    - `DEFAULT_FROM_EMAIL`
- Q11: Chon bo man hinh MVP day du hon.
  - Trang chu / danh sach viec lam.
  - Trang chi tiet viec lam.
  - Dang ky / dang nhap / dang xuat.
  - Dashboard Candidate.
  - Dashboard Recruiter.
  - Ho so ca nhan Candidate.
  - Trang cong ty.
  - Form tao/sua bai tuyen dung.
  - Danh sach job da luu.
  - Lich su ung tuyen.
  - Danh sach ung vien theo job.
  - Trang cap nhat trang thai ung vien.
  - Trang upload/quan ly CV rieng.
  - Dashboard thong ke co ban cho recruiter.
- Q12: Chon tach 2 trang dang ky va Recruiter tao cong ty ngay khi dang ky.
  - Candidate dang ky tai `/candidate/register/`.
  - Recruiter dang ky tai `/recruiter/register/`.
  - Form Recruiter registration bao gom thong tin tai khoan recruiter va thong tin cong ty.
  - Sau dang nhap, redirect theo role:
    - Candidate -> Candidate dashboard.
    - Recruiter -> Recruiter dashboard.
  - Mot recruiter trong MVP gan voi mot company chinh.
- Q13 update CandidateProfile:
  - Bo field "vi tri mong muon".
  - Doi "dia diem mong muon" thanh "khu vuc lam viec".
- Q13: Chot dung danh sach field hien tai cho CandidateProfile, Company va JobPost.
- Q14: Chon Django ORM search/filter cho MVP.
  - Chua dung Elasticsearch trong MVP.
  - Search/filter job bang Django QuerySet.
  - Filter du kien: tu khoa, cong ty, ky nang, dia diem, hinh thuc lam viec, loai cong viec.
  - Search candidate trong recruiter dashboard co the dung filter tren profile/application/CV text da extract.
- Q15: Chon xu ly AI/ATS dong bo ngay trong request cho MVP.
  - Khi candidate upload/apply CV, he thong extract PDF va tinh semantic matching ngay.
  - Uu diem: de code, de demo, khong can Redis/Celery worker.
  - Nhuoc diem: request co the cham neu model tai lan dau hoac CV dai.
  - Can tach logic ATS thanh service rieng de sau nay co the chuyen sang Celery.
- Q16 partial:
  - Giao dien dung Bootstrap 5 qua CDN.
  - Can seed data mau de demo nhanh.
  - Co dung Django Admin va dang ky cac model chinh vao admin.

## 16. Cau hoi dang cho tra loi

### Q16. Giao dien, admin va test

Da chot cac quy uoc cuoi truoc khi code:

- Giao dien dung Bootstrap 5 qua CDN.
- Co Django Admin tai `/admin/` de quan tri du lieu.
- Dang ky cac model chinh vao Django Admin.
- Co seed data mau de demo nhanh.

## 20. Field model MVP da chot

### CandidateProfile

- Ho ten
- So dien thoai
- Khu vuc lam viec
- Ky nang
- Gioi thieu ban than

### Company

- Ten cong ty
- Logo
- Website
- Dia chi
- Quy mo cong ty
- Mo ta cong ty

### JobPost

- Tieu de
- Cong ty
- Dia diem
- Hinh thuc lam viec: onsite/remote/hybrid
- Loai cong viec: full-time/part-time/intern/contract
- Muc luong min/max
- Ky nang yeu cau
- Mo ta cong viec
- Yeu cau ung vien
- Quyen loi
- Han ung tuyen
- Trang thai active/inactive

## 17. Yeu cau MVP sau khi chot

- Auth va phan quyen:
  - Dang ky / dang nhap
  - Django session authentication
  - Role Candidate
  - Role Recruiter
- Candidate:
  - Quan ly ho so ca nhan muc co ban
  - Xem danh sach viec lam
  - Search/filter job
  - Luu job yeu thich
  - Upload CV PDF
  - Luu file CV bang local storage trong `media/`
  - Database luu duong dan file CV de truy xuat
  - Apply cong viec
  - Theo doi trang thai ung tuyen bang UI tieng Viet
- Recruiter:
  - Tao/cong khai thong tin cong ty
  - Tao/sua/xoa bai tuyen dung
  - Xem danh sach ung vien apply vao tung job
  - Cap nhat trang thai ung tuyen
  - Xem ATS score semantic matching
- AI ATS MVP:
  - Extract text tu CV PDF
  - Chi xu ly PDF co text that, chua OCR file scan anh
  - Ho tro CV va Job Description tieng Viet/tieng Anh
  - Tao embedding cho CV text va Job Description bang multilingual `sentence-transformers`
  - Tinh ATS score dua tren semantic similarity
  - Extract skill/keyword de ho tro hien thi ly do matching va ky nang con thieu
- Email:
  - Gui email that qua Gmail SMTP
  - Gui email thong bao cho ung vien khi apply thanh cong
  - Gui email thong bao cho ung vien khi trang thai ung tuyen thay doi
- Dashboard:
  - So luong job da dang
  - So luong application
  - Thong ke application theo trang thai
  - Top ung vien theo ATS score

## 19. Man hinh MVP da chot

- Trang chu / danh sach viec lam
- Trang chi tiet viec lam
- Dang ky / dang nhap / dang xuat
- Dashboard Candidate
- Dashboard Recruiter
- Ho so ca nhan Candidate
- Trang cong ty
- Form tao/sua bai tuyen dung
- Danh sach job da luu
- Lich su ung tuyen
- Danh sach ung vien theo job
- Trang cap nhat trang thai ung vien
- Trang upload/quan ly CV rieng
- Dashboard thong ke co ban cho recruiter

## 18. Ghi chu trien khai

- Da tien hanh code MVP Django trong workspace hien tai.
- Project Django: `ats_site`
- App chinh: `recruitment`
- Database local: `db.sqlite3`
- Media upload: `media/`
- Semantic matching dung model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` qua HuggingFace `transformers` de tranh loi crash wrapper `sentence-transformers` tren moi truong Windows hien tai.
- Da co seed command: `python manage.py seed_demo`
- Da co README huong dan chay: `README.md`
