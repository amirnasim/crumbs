from django.contrib import messages
from django.shortcuts import redirect, render

from careers.constants import HR_QUESTIONS
from careers.forms import CareerApplicationForm
from careers.notifications import log_new_career_application

SUCCESS_MESSAGE = (
    "درخواست همکاری شما با موفقیت ثبت شد.\n"
    "در صورت نیاز، تیم Crumbs با شما تماس خواهد گرفت."
)


def careers(request):
    form = CareerApplicationForm()

    if request.method == "POST":
        form = CareerApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            application = form.save()
            log_new_career_application(application)
            messages.success(request, SUCCESS_MESSAGE)
            return redirect("careers:careers")

    return render(
        request,
        "pages/careers.html",
        {
            "form": form,
            "hr_field_rows": [
                {
                    "key": key,
                    "label": label,
                    "field": form[f"hr_{key}"],
                }
                for key, label in HR_QUESTIONS
            ],
        },
    )
