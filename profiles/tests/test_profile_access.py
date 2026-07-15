from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.services.storage import get_private_storage
from core.tests.utils import make_user


class PrivateProfilePhotoTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.profile = self.user.athlete_profile
        self.profile.profile_photo.save(
            "avatar.png",
            SimpleUploadedFile("avatar.png", b"private-photo", content_type="image/png"),
        )

    def tearDown(self):
        if self.profile.profile_photo:
            get_private_storage().delete(self.profile.profile_photo.name)

    def test_private_photo_disables_shared_caching(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profiles:photo", args=[self.user.uuid]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        response.close()
