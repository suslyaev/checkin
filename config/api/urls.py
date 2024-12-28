from rest_framework import routers
from .api import ModuleInstanceViewSet, ActionSerializerViewSet, ContactSerializerViewSet

router = routers.DefaultRouter()
router.register('events', ModuleInstanceViewSet)
router.register('actions', ActionSerializerViewSet)
router.register('contacts', ContactSerializerViewSet)

urlpatterns = router.urls