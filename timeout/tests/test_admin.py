"""
Tests for the custom UserAdmin configuration in the timeout app.
Includes tests to verify that the admin interface is correctly set up with the expected fields, filters, and fieldsets, as well as that the admin changelist view loads successfully.
"""
from django.contrib.admin.sites import AdminSite
from django.test import TestCase
from django.contrib.auth import get_user_model

from timeout.admin import UserAdmin

User = get_user_model()


class UserAdminTests(TestCase):
    """Tests for the custom UserAdmin configuration."""

    def setUp(self):
        """Set up test data for UserAdminTests."""
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)
        self.superuser = User.objects.create_superuser(
            username='admin', email='admin@test.com', password='Admin@1234'
        )

    def test_list_display(self):
        """Test that list_display includes the expected fields."""
        self.assertIn('university', self.admin.list_display)
        self.assertIn('year_of_study', self.admin.list_display)

    def test_list_filter_includes_custom_fields(self):
        """Test that list_filter includes the expected custom fields."""
        filters = self.admin.list_filter
        self.assertIn('university', filters)
        self.assertIn('management_style', filters)
        self.assertIn('privacy_private', filters)

    def test_search_fields_includes_university(self):
        """Test that search_fields includes 'university'."""
        self.assertIn('university', self.admin.search_fields)

    def test_custom_fieldsets_present(self):
        """Test that custom fieldsets are present."""
        fieldset_names = [fs[0] for fs in self.admin.fieldsets]
        self.assertIn('Profile', fieldset_names)
        self.assertIn('Preferences', fieldset_names)
        self.assertIn('Social', fieldset_names)

    def test_add_fieldsets_present(self):
        """Test that add_fieldsets are present."""
        fieldset_names = [fs[0] for fs in self.admin.add_fieldsets]
        self.assertIn('Profile', fieldset_names)

    def test_admin_changelist_loads(self):
        """Test that the admin changelist view loads successfully."""
        self.client.force_login(self.superuser)
        response = self.client.get('/admin/timeout/user/')
        self.assertEqual(response.status_code, 200)
