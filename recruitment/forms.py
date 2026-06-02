from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction

from .models import (
    Application,
    CandidateProfile,
    Company,
    CVDocument,
    JobPost,
    RecruiterProfile,
)


class BootstrapFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            if isinstance(field.widget, forms.CheckboxInput):
                css_class = "form-check-input"
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {css_class}".strip()


class VietnameseAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(label="Tên đăng nhập")
    password = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput)


class CandidateRegistrationForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(label="Email")
    full_name = forms.CharField(label="Họ tên", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=30, required=False)
    work_area = forms.CharField(label="Khu vực làm việc", max_length=120, required=False)
    skills = forms.CharField(label="Kỹ năng", widget=forms.Textarea(attrs={"rows": 3}), required=False)
    summary = forms.CharField(label="Giới thiệu bản thân", widget=forms.Textarea(attrs={"rows": 4}), required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")
        labels = {"username": "Tên đăng nhập"}

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            CandidateProfile.objects.create(
                user=user,
                full_name=self.cleaned_data["full_name"],
                phone=self.cleaned_data.get("phone", ""),
                work_area=self.cleaned_data.get("work_area", ""),
                skills=self.cleaned_data.get("skills", ""),
                summary=self.cleaned_data.get("summary", ""),
            )
        return user


class RecruiterRegistrationForm(BootstrapFormMixin, UserCreationForm):
    email = forms.EmailField(label="Email")
    full_name = forms.CharField(label="Họ tên người tuyển dụng", max_length=150)
    phone = forms.CharField(label="Số điện thoại", max_length=30, required=False)
    company_name = forms.CharField(label="Tên công ty", max_length=180)
    company_logo = forms.FileField(label="Logo", required=False)
    company_website = forms.URLField(label="Website", required=False)
    company_address = forms.CharField(label="Địa chỉ", max_length=255, required=False)
    company_size = forms.CharField(label="Quy mô công ty", max_length=80, required=False)
    company_description = forms.CharField(
        label="Mô tả công ty",
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")
        labels = {"username": "Tên đăng nhập"}

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            RecruiterProfile.objects.create(
                user=user,
                full_name=self.cleaned_data["full_name"],
                phone=self.cleaned_data.get("phone", ""),
            )
            Company.objects.create(
                recruiter=user,
                name=self.cleaned_data["company_name"],
                logo=self.cleaned_data.get("company_logo"),
                website=self.cleaned_data.get("company_website", ""),
                address=self.cleaned_data.get("company_address", ""),
                company_size=self.cleaned_data.get("company_size", ""),
                description=self.cleaned_data.get("company_description", ""),
            )
        return user


class CandidateProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CandidateProfile
        fields = ("full_name", "phone", "work_area", "skills", "summary")
        labels = {
            "full_name": "Họ tên",
            "phone": "Số điện thoại",
            "work_area": "Khu vực làm việc",
            "skills": "Kỹ năng",
            "summary": "Giới thiệu bản thân",
        }
        widgets = {
            "skills": forms.Textarea(attrs={"rows": 3}),
            "summary": forms.Textarea(attrs={"rows": 4}),
        }


class CompanyForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = ("name", "logo", "website", "address", "company_size", "description")
        labels = {
            "name": "Tên công ty",
            "logo": "Logo",
            "website": "Website",
            "address": "Địa chỉ",
            "company_size": "Quy mô công ty",
            "description": "Mô tả công ty",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class JobPostForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = JobPost
        fields = (
            "title",
            "location",
            "work_mode",
            "job_type",
            "salary_min",
            "salary_max",
            "required_skills",
            "description",
            "requirements",
            "benefits",
            "deadline",
            "is_active",
        )
        labels = {
            "title": "Tiêu đề",
            "location": "Địa điểm",
            "work_mode": "Hình thức làm việc",
            "job_type": "Loại công việc",
            "salary_min": "Lương tối thiểu",
            "salary_max": "Lương tối đa",
            "required_skills": "Kỹ năng yêu cầu",
            "description": "Mô tả công việc",
            "requirements": "Yêu cầu ứng viên",
            "benefits": "Quyền lợi",
            "deadline": "Hạn ứng tuyển",
            "is_active": "Đang tuyển",
        }
        widgets = {
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "required_skills": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 5}),
            "requirements": forms.Textarea(attrs={"rows": 5}),
            "benefits": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned = super().clean()
        salary_min = cleaned.get("salary_min")
        salary_max = cleaned.get("salary_max")
        if salary_min and salary_max and salary_min > salary_max:
            raise forms.ValidationError("Lương tối thiểu không được lớn hơn lương tối đa.")
        return cleaned


class CVUploadForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = CVDocument
        fields = ("title", "file")
        labels = {"title": "Tên CV", "file": "File CV PDF"}

    def clean_file(self):
        file_obj = self.cleaned_data["file"]
        if not file_obj.name.lower().endswith(".pdf"):
            raise forms.ValidationError("MVP chỉ nhận file CV PDF.")
        return file_obj


class ApplicationForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("cv", "cover_letter")
        labels = {"cv": "Chọn CV", "cover_letter": "Lời nhắn cho nhà tuyển dụng"}
        widgets = {"cover_letter": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, candidate=None, **kwargs):
        super().__init__(*args, **kwargs)
        if candidate:
            self.fields["cv"].queryset = candidate.cv_documents.all()


class ApplicationStatusForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Application
        fields = ("status", "review_status", "manual_score", "recruiter_note")
        labels = {
            "status": "Trạng thái ứng tuyển",
            "review_status": "Đánh giá thủ công",
            "manual_score": "Điểm thủ công",
            "recruiter_note": "Ghi chú recruiter",
        }
        widgets = {
            "recruiter_note": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_manual_score(self):
        score = self.cleaned_data.get("manual_score")
        if score is not None and not 1 <= score <= 5:
            raise forms.ValidationError("Điểm thủ công phải từ 1 đến 5.")
        return score
