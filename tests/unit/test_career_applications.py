"""Careers app — café hiring applications (Persian public UI)."""

import logging

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from careers.admin import CareerApplicationAdmin
from careers.constants import (
    AGE_RANGE_ERROR,
    FILE_SIZE_ERROR,
    HR_QUESTIONS,
    INVALID_PDF_ERROR,
    MAX_RESUME_SIZE_BYTES,
    PDF_ONLY_ERROR,
    REQUIRED_FIELD_ERROR,
)
from careers.forms import CareerApplicationForm
from careers.models import CareerApplication

User = get_user_model()

VALID_APPLICATION_DATA = {
    "full_name": "Sara Ahmadi",
    "phone": "09121234567",
    "email": "sara@example.com",
    "age": 25,
    "residential_area": "سعادت‌آباد",
    "desired_position": CareerApplication.DesiredPosition.BARISTA,
    "employment_type": CareerApplication.EmploymentType.FULL_TIME,
    "years_of_experience": 2,
    "relevant_experience": "دو سال سابقه کار به عنوان باریستا.",
    "hr_why_crumbs": "علاقه‌مند به فضای کافه Crumbs هستم.",
    "hr_cafe_experience": "دو سال در یک کافه محلی کار کرده‌ام.",
    "hr_start_timing": "از ابتدای ماه آینده.",
}

PUBLIC_ENGLISH_MARKERS = (
    "Submit Application",
    "HR Questions",
    "Your details",
    "Work With Us",
    "Full Name",
    "Phone Number",
    "Desired Position",
    "Resume Upload",
    "placeholder=",
    ">Careers<",
    "Careers /",
    "shift_availability",
    "شیفت‌های مختلف",
    "available_from",
    "تاریخ شروع همکاری",
    "ایمیل (اختیاری)",
)

SHOP_CATEGORY_MARKERS = (
    'data-default-category="cookies"',
    'data-menu-panel="cookies"',
    'id="menu-panel-cookies"',
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="career-admin",
        email="career-admin@example.com",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def career_admin():
    return CareerApplicationAdmin(CareerApplication, admin.site)


def _admin_request(rf, user):
    request = rf.post("/admin/careers/careerapplication/")
    request.user = user
    middleware = SessionMiddleware(lambda req: HttpResponse())
    middleware.process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


def _drawer_html(client: Client) -> str:
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    return response.content.decode()


def _make_application(**overrides):
    data = {
        "full_name": "Ali Rezaei",
        "phone": "09120001122",
        "email": "ali@example.com",
        "age": 28,
        "residential_area": "پاسداران",
        "desired_position": CareerApplication.DesiredPosition.KITCHEN_STAFF,
        "employment_type": CareerApplication.EmploymentType.FULL_TIME,
        "years_of_experience": 3,
        "relevant_experience": "سابقه کار در آشپزخانه.",
        "hr_answers": {"why_crumbs": "کار در آشپزخانه."},
    }
    data.update(overrides)
    return CareerApplication.objects.create(**data)


@pytest.mark.django_db
class TestCareersTemplateSyntax:
    def test_careers_templates_compile_without_syntax_error(self):
        from django.template.loader import get_template

        get_template("pages/careers.html")
        get_template("partials/careers_application_form.html")


@pytest.mark.django_db
class TestCareersPersianLocalization:
    def test_careers_page_uses_persian_copy(self, client):
        response = client.get(reverse("careers:careers"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "همکاری با ما" in content
        assert "اگر علاقه‌مند به همکاری در تیم Crumbs هستید، فرم زیر را تکمیل کنید." in content
        assert (
            "ما همیشه به دنبال افراد پرانرژی، مسئولیت‌پذیر و "
            "علاقه‌مند به فعالیت در محیط کافه و بیکری هستیم."
        ) in content
        assert "اطلاعات فردی" in content
        assert "اطلاعات شغلی" in content
        assert "سؤالات استخدامی" in content
        assert "نام و نام خانوادگی" in content
        assert "سن" in content
        assert "منطقه زندگی" in content
        assert "موقعیت شغلی مورد نظر" in content
        assert "شماره تلفن همراه" in content
        assert "نوع همکاری" in content
        assert "سابقه کار مرتبط" in content
        assert "بارگذاری رزومه (PDF)" in content
        assert "فقط فایل PDF" in content
        assert "حداکثر حجم ۵ مگابایت" in content
        assert "ارسال درخواست همکاری" in content
        assert "career-form-card" in content
        assert "career-form-textarea" in content

        for _key, label in HR_QUESTIONS:
            assert content.count(label) == 1

        for marker in PUBLIC_ENGLISH_MARKERS:
            assert marker not in content

    def test_form_labels_are_persian(self):
        form = CareerApplicationForm()

        assert form.fields["full_name"].label == "نام و نام خانوادگی"
        assert form.fields["phone"].label == "شماره تلفن همراه"
        assert form.fields["email"].label == "ایمیل"
        assert form.fields["email"].required is True
        assert form.fields["age"].label == "سن"
        assert form.fields["residential_area"].label == "منطقه زندگی"
        assert form.fields["desired_position"].label == "موقعیت شغلی مورد نظر"
        assert form.fields["employment_type"].label == "نوع همکاری"
        assert form.fields["years_of_experience"].label == "سابقه کار (سال)"
        assert form.fields["relevant_experience"].label == "سابقه کار مرتبط"
        assert form.fields["resume_file"].label == "بارگذاری رزومه (PDF)"
        assert form.fields["desired_position"].empty_label == "انتخاب کنید"
        assert form.fields["employment_type"].empty_label == "انتخاب کنید"
        assert "available_from" not in form.fields
        assert "hr_shift_availability" not in form.fields

    def test_form_widgets_have_no_placeholders(self):
        form = CareerApplicationForm()

        for field_name, field in form.fields.items():
            widget = field.widget
            attrs = getattr(widget, "attrs", {})
            assert "placeholder" not in attrs, field_name

    def test_position_and_employment_choices_are_persian(self):
        position_labels = dict(CareerApplication.DesiredPosition.choices)
        employment_labels = dict(CareerApplication.EmploymentType.choices)

        assert position_labels["barista"] == "باریستا"
        assert position_labels["cashier"] == "صندوق‌دار / فروشنده"
        assert position_labels["cold_bar"] == "بار سرد"
        assert employment_labels["full_time"] == "تمام‌وقت"
        assert employment_labels["part_time"] == "پاره‌وقت"

    def test_careers_page_shows_updated_position_labels(self, client):
        response = client.get(reverse("careers:careers"))
        content = response.content.decode()

        assert "صندوق‌دار / فروشنده" in content
        assert "بار سرد" in content
        assert "ایمیل (اختیاری)" not in content


@pytest.mark.django_db
class TestCareersHasNoSocialFields:
    def test_model_excludes_github_and_linkedin(self):
        field_names = {field.name for field in CareerApplication._meta.get_fields()}

        assert "github_url" not in field_names
        assert "linkedin_url" not in field_names
        assert "available_from" not in field_names

    def test_careers_page_has_no_social_field_labels(self, client):
        response = client.get(reverse("careers:careers"))
        content = response.content.decode().lower()

        assert response.status_code == 200
        assert "github" not in content
        assert "linkedin" not in content


@pytest.mark.django_db
class TestCareerApplicationModel:
    def test_str_uses_persian_position_label(self):
        application = CareerApplication(
            full_name="Ali Rezaei",
            phone="09120001122",
            age=28,
            residential_area="پاسداران",
            desired_position=CareerApplication.DesiredPosition.KITCHEN_STAFF,
            employment_type=CareerApplication.EmploymentType.FULL_TIME,
            years_of_experience=3,
            relevant_experience="آشپزخانه.",
            hr_answers={"why_crumbs": "کار در آشپزخانه."},
        )

        assert str(application) == "Ali Rezaei — نیروی آشپزخانه"

    def test_default_status_is_new(self):
        application = _make_application(
            full_name="Neda Karimi",
            phone="09123334455",
            desired_position=CareerApplication.DesiredPosition.CASHIER,
            years_of_experience=1,
            hr_answers={"why_crumbs": "خدمات مشتری."},
        )

        assert application.status == CareerApplication.Status.NEW


@pytest.mark.django_db
class TestCareerApplicationForm:
    def test_valid_form_builds_hr_answers_and_stores_relevant_experience_separately(self):
        form = CareerApplicationForm(data=VALID_APPLICATION_DATA)

        assert form.is_valid(), form.errors
        application = form.save()

        assert application.hr_answers["why_crumbs"] == VALID_APPLICATION_DATA["hr_why_crumbs"]
        assert application.hr_answers["start_timing"] == VALID_APPLICATION_DATA["hr_start_timing"]
        assert "shift_availability" not in application.hr_answers
        assert application.relevant_experience == VALID_APPLICATION_DATA["relevant_experience"]
        assert application.employment_type == CareerApplication.EmploymentType.FULL_TIME
        assert application.age == 25
        assert application.residential_area == "سعادت‌آباد"

    def test_rejects_age_outside_range(self):
        data = {**VALID_APPLICATION_DATA, "age": 15}
        form = CareerApplicationForm(data=data)

        assert not form.is_valid()
        assert AGE_RANGE_ERROR in form.errors["age"]

    def test_rejects_non_pdf_with_persian_message(self):
        data = {**VALID_APPLICATION_DATA}
        files = {
            "resume_file": SimpleUploadedFile(
                "resume.docx",
                b"not-a-pdf",
                content_type="application/msword",
            )
        }
        form = CareerApplicationForm(data=data, files=files)

        assert not form.is_valid()
        assert PDF_ONLY_ERROR in form.errors["resume_file"]

    def test_rejects_oversized_pdf_with_persian_message(self):
        data = {**VALID_APPLICATION_DATA}
        files = {
            "resume_file": SimpleUploadedFile(
                "resume.pdf",
                b"%PDF-1.4 " + b"x" * (MAX_RESUME_SIZE_BYTES + 1),
                content_type="application/pdf",
            )
        }
        form = CareerApplicationForm(data=data, files=files)

        assert not form.is_valid()
        assert FILE_SIZE_ERROR in form.errors["resume_file"]

    def test_rejects_renamed_text_file_with_pdf_extension(self):
        data = {**VALID_APPLICATION_DATA}
        files = {
            "resume_file": SimpleUploadedFile(
                "resume.pdf",
                b"plain text content",
                content_type="application/pdf",
            )
        }
        form = CareerApplicationForm(data=data, files=files)

        assert not form.is_valid()
        assert INVALID_PDF_ERROR in form.errors["resume_file"]

    def test_missing_resume_is_allowed(self):
        form = CareerApplicationForm(data=VALID_APPLICATION_DATA)

        assert form.is_valid(), form.errors
        application = form.save()
        assert not application.resume_file

    def test_valid_pdf_resets_file_pointer_after_header_check(self):
        data = {**VALID_APPLICATION_DATA}
        resume = SimpleUploadedFile(
            "resume.pdf",
            b"%PDF-1.4 valid content",
            content_type="application/pdf",
        )
        files = {"resume_file": resume}
        form = CareerApplicationForm(data=data, files=files)

        assert form.is_valid(), form.errors
        assert form.cleaned_data["resume_file"].read() == b"%PDF-1.4 valid content"

    def test_required_field_uses_persian_message(self):
        data = {**VALID_APPLICATION_DATA, "full_name": ""}
        form = CareerApplicationForm(data=data)

        assert not form.is_valid()
        assert REQUIRED_FIELD_ERROR in form.errors["full_name"]

    def test_email_is_required(self):
        data = {**VALID_APPLICATION_DATA, "email": ""}
        form = CareerApplicationForm(data=data)

        assert not form.is_valid()
        assert REQUIRED_FIELD_ERROR in form.errors["email"]

    def test_cold_bar_is_valid_position(self):
        data = {
            **VALID_APPLICATION_DATA,
            "desired_position": CareerApplication.DesiredPosition.COLD_BAR,
            "relevant_experience": "یک سال کار در بار سرد.",
        }
        form = CareerApplicationForm(data=data)

        assert form.is_valid(), form.errors
        application = form.save()
        assert application.desired_position == CareerApplication.DesiredPosition.COLD_BAR
        assert application.get_desired_position_display() == "بار سرد"

    def test_accepts_valid_pdf(self):
        data = {**VALID_APPLICATION_DATA}
        files = {
            "resume_file": SimpleUploadedFile(
                "resume.pdf",
                b"%PDF-1.4 test",
                content_type="application/pdf",
            )
        }
        form = CareerApplicationForm(data=data, files=files)

        assert form.is_valid(), form.errors


@pytest.mark.django_db
class TestCareersPage:
    def test_careers_get_returns_200(self, client):
        response = client.get(reverse("careers:careers"))
        assert response.status_code == 200

    def test_valid_post_creates_application_and_shows_persian_success_message(self, client):
        response = client.post(reverse("careers:careers"), data=VALID_APPLICATION_DATA)

        assert response.status_code == 302
        assert response.url == reverse("careers:careers")
        application = CareerApplication.objects.get()
        assert application.full_name == "Sara Ahmadi"
        assert application.age == 25
        assert application.residential_area == "سعادت‌آباد"
        assert application.relevant_experience == VALID_APPLICATION_DATA["relevant_experience"]
        assert "shift_availability" not in application.hr_answers

        follow = client.get(response.url)
        content = follow.content.decode()
        assert "درخواست همکاری شما با موفقیت ثبت شد." in content
        assert "در صورت نیاز، تیم Crumbs با شما تماس خواهد گرفت." in content

    def test_required_fields_validated(self, client):
        invalid_data = {**VALID_APPLICATION_DATA, "full_name": "", "hr_why_crumbs": ""}
        response = client.post(reverse("careers:careers"), data=invalid_data)

        assert response.status_code == 200
        assert CareerApplication.objects.count() == 0
        form = response.context["form"]
        assert "full_name" in form.errors
        assert "hr_why_crumbs" in form.errors

    def test_submission_is_logged(self, client, caplog):
        with caplog.at_level(logging.INFO, logger="careers.notifications"):
            response = client.post(reverse("careers:careers"), data=VALID_APPLICATION_DATA)

        assert response.status_code == 302
        assert any("New career application" in record.message for record in caplog.records)


@pytest.mark.django_db
class TestCareerApplicationAdmin:
    def test_admin_list_shows_new_columns(self, client, staff_user):
        _make_application(full_name="Ali Rezaei")
        client.force_login(staff_user)

        response = client.get(reverse("admin:careers_careerapplication_changelist"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "Ali Rezaei" in content
        assert "پاسداران" in content

    def test_admin_actions_update_status(self, rf, staff_user, career_admin):
        application = _make_application(
            full_name="Neda Karimi",
            phone="09123334455",
            desired_position=CareerApplication.DesiredPosition.WAITER,
            years_of_experience=0,
            hr_answers={"why_crumbs": "خدمات مهمان."},
        )
        queryset = CareerApplication.objects.filter(pk=application.pk)
        request = _admin_request(rf, staff_user)

        career_admin.mark_interview(request, queryset)
        application.refresh_from_db()
        assert application.status == CareerApplication.Status.INTERVIEW

        career_admin.mark_hired(request, queryset)
        application.refresh_from_db()
        assert application.status == CareerApplication.Status.HIRED


@pytest.mark.django_db
class TestNavigationDrawer:
    def test_drawer_contains_persian_careers_link(self, client):
        content = _drawer_html(client)

        assert "همکاری با ما" in content
        assert reverse("careers:careers") in content
        assert "Careers" not in content

    def test_drawer_does_not_contain_category_links(self, client):
        content = _drawer_html(client)
        drawer_start = content.index('id="menu-drawer"')
        drawer_end = content.index("</aside>", drawer_start)
        drawer = content[drawer_start:drawer_end]

        assert "menu-drawer__list--categories" not in drawer
        for label in ("Cookies", "Coffee", "Food", "Salads", "Drinks"):
            assert f">{label}</a>" not in drawer


@pytest.mark.django_db
class TestShopCategorySections:
    def test_shop_page_still_has_category_sections(self, client):
        response = client.get(reverse("products:product_list"))

        assert response.status_code == 200
        content = response.content.decode()
        for marker in SHOP_CATEGORY_MARKERS:
            assert marker in content
