# academics/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied

class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = "people:login"
    def test_func(self):
        return getattr(self.request.user, "is_admin", False)
    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            raise PermissionDenied("No tenés permiso para ver esta página.")
        return super().handle_no_permission()
