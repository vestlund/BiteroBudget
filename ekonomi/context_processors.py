from .models import Transaktion


def meny(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}
    return {"antal_okategoriserade": Transaktion.objects.okategoriserade().count()}
