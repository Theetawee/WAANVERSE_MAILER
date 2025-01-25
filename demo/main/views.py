from django.shortcuts import render

from waanverse_mailer.email_service import EmailService

# Create your views here.


def index(request):
    email_service = EmailService()
    email_service.send_email(
        recipient_list="test@example.com",
        subject="Test Subject",
        template_name="single_email",
        context={"name": "John"},
    )
    return render(request, "index.html")
