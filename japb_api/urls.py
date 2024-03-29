from django.conf import settings
from django.urls import path, re_path, include, reverse_lazy
from django.conf.urls.static import static
from django.contrib import admin
from django.views.generic.base import RedirectView
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken import views
from .users.views import UserViewSet, UserCreateViewSet
from .currencies.views import CurrencyViewSet
from .accounts.views import AccountViewSet
from .transactions.views import TransactionViewSet, CurrencyExchangeViewSet, CategoryViewSet
from .receivables.views import ReceivableViewSet
from .reports.views import ReportAccountViewSet, ReportCurrencyViewSet
from .products.views import ProductsViewSet, ProductsListViewSet, ProductListItemViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'users', UserCreateViewSet)
router.register(r'currencies', CurrencyViewSet, basename='currencies')
router.register(r'accounts', AccountViewSet, basename='accounts')
router.register(r'transactions', TransactionViewSet, basename='transactions')
router.register(r'categories', CategoryViewSet, basename='categories')
router.register(r'exchanges', CurrencyExchangeViewSet, basename='exchanges')
router.register(r'receivables', ReceivableViewSet, basename='receivables')

router.register(r'reports', ReportAccountViewSet, basename='reports')
router.register(r'reports-currency', ReportCurrencyViewSet, basename='reports-currency')

router.register(r'products', ProductsViewSet, basename='products')
router.register(r'products-list', ProductsListViewSet, basename='products-list')
router.register(r'products-list-item', ProductListItemViewSet, basename='products-list-item')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api-token-auth/', views.obtain_auth_token),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # the 'api-root' from django rest-frameworks default router
    # http://www.django-rest-framework.org/api-guide/routers/#defaultrouter
    re_path(r'^$', RedirectView.as_view(url=reverse_lazy('api-root'), permanent=False)),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
