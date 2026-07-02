from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator

from careers.constants import (
    AGE_RANGE_ERROR,
    FILE_SIZE_ERROR,
    HR_QUESTIONS,
    INVALID_PDF_ERROR,
    MAX_AGE,
    MAX_RESUME_SIZE_BYTES,
    MIN_AGE,
    PDF_MAGIC,
    PDF_ONLY_ERROR,
    REQUIRED_FIELD_ERROR,
)
from careers.models import CareerApplication

FORM_CONTROL_CLASS = "form-control"
TEXTAREA_CLASS = "form-control career-form-textarea"


class CareerApplicationForm(forms.ModelForm):
    class Meta:
        model = CareerApplication
        fields = (
            "full_name",
            "phone",
            "email",
            "age",
            "residential_area",
            "desired_position",
            "employment_type",
            "years_of_experience",
            "relevant_experience",
            "resume_file",
        )
        widgets = {
            "full_name": forms.TextInput(attrs={"class": FORM_CONTROL_CLASS, "autocomplete": "name"}),
            "phone": forms.TextInput(
                attrs={"class": FORM_CONTROL_CLASS, "dir": "ltr", "autocomplete": "tel"}
            ),
            "email": forms.EmailInput(
                attrs={"class": FORM_CONTROL_CLASS, "dir": "ltr", "autocomplete": "email"}
            ),
            "age": forms.NumberInput(
                attrs={
                    "class": FORM_CONTROL_CLASS,
                    "min": MIN_AGE,
                    "max": MAX_AGE,
                    "inputmode": "numeric",
                }
            ),
            "residential_area": forms.TextInput(attrs={"class": FORM_CONTROL_CLASS}),
            "desired_position": forms.Select(attrs={"class": FORM_CONTROL_CLASS}),
            "employment_type": forms.Select(attrs={"class": FORM_CONTROL_CLASS}),
            "years_of_experience": forms.NumberInput(
                attrs={"class": FORM_CONTROL_CLASS, "min": 0, "max": 50, "inputmode": "numeric"}
            ),
            "relevant_experience": forms.Textarea(
                attrs={"class": TEXTAREA_CLASS, "rows": 4}
            ),
            "resume_file": forms.FileInput(
                attrs={"class": "form-control career-form-file", "accept": ".pdf,application/pdf"}
            ),
        }
        labels = {
            "full_name": "نام و نام خانوادگی",
            "phone": "شماره تلفن همراه",
            "email": "ایمیل",
            "age": "سن",
            "residential_area": "منطقه زندگی",
            "desired_position": "موقعیت شغلی مورد نظر",
            "employment_type": "نوع همکاری",
            "years_of_experience": "سابقه کار (سال)",
            "relevant_experience": "سابقه کار مرتبط",
            "resume_file": "بارگذاری رزومه (PDF)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.error_messages["required"] = REQUIRED_FIELD_ERROR
        self.fields["desired_position"].empty_label = "انتخاب کنید"
        self.fields["employment_type"].empty_label = "انتخاب کنید"
        self.fields["age"].validators = [
            MinValueValidator(MIN_AGE, message=AGE_RANGE_ERROR),
            MaxValueValidator(MAX_AGE, message=AGE_RANGE_ERROR),
        ]
        for key, label in HR_QUESTIONS:
            field_name = f"hr_{key}"
            self.fields[field_name] = forms.CharField(
                label=label,
                widget=forms.Textarea(
                    attrs={
                        "class": TEXTAREA_CLASS,
                        "rows": 4,
                    }
                ),
            )
            if self.instance.pk and self.instance.hr_answers:
                self.fields[field_name].initial = self.instance.hr_answers.get(key, "")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            raise forms.ValidationError(REQUIRED_FIELD_ERROR)
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get("phone") or "").strip()
        if not phone:
            raise forms.ValidationError(REQUIRED_FIELD_ERROR)
        return phone

    def clean_full_name(self):
        full_name = (self.cleaned_data.get("full_name") or "").strip()
        if not full_name:
            raise forms.ValidationError(REQUIRED_FIELD_ERROR)
        return full_name

    def clean_residential_area(self):
        residential_area = (self.cleaned_data.get("residential_area") or "").strip()
        if not residential_area:
            raise forms.ValidationError(REQUIRED_FIELD_ERROR)
        return residential_area

    def clean_relevant_experience(self):
        relevant_experience = (self.cleaned_data.get("relevant_experience") or "").strip()
        if not relevant_experience:
            raise forms.ValidationError(REQUIRED_FIELD_ERROR)
        return relevant_experience

    def clean_resume_file(self):
        resume = self.cleaned_data.get("resume_file")
        if not resume:
            return resume

        if resume.size > MAX_RESUME_SIZE_BYTES:
            raise forms.ValidationError(FILE_SIZE_ERROR)

        if not resume.name.lower().endswith(".pdf"):
            raise forms.ValidationError(PDF_ONLY_ERROR)

        header = resume.read(len(PDF_MAGIC))
        resume.seek(0)
        if header != PDF_MAGIC:
            raise forms.ValidationError(INVALID_PDF_ERROR)

        return resume

    def clean(self):
        cleaned = super().clean()
        hr_answers = {}
        for key, _label in HR_QUESTIONS:
            field_name = f"hr_{key}"
            answer = (cleaned.get(field_name) or "").strip()
            if not answer:
                self.add_error(field_name, REQUIRED_FIELD_ERROR)
            else:
                hr_answers[key] = answer
        cleaned["hr_answers"] = hr_answers
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.hr_answers = self.cleaned_data.get("hr_answers", {})
        if commit:
            instance.save()
        return instance
