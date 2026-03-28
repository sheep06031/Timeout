"""
sitemaps.py - Defines StaticViewSitemap for generating a sitemap of static views with monthly change frequency and priority.
"""


from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static views with monthly change frequency and 0.8 priority."""
    changefreq = 'monthly'
    priority = 0.8

    def items(self):
        """Return list of static view names for sitemap."""
        return ['landing']

    def location(self, item):
        """Get the URL for a static view by reversing its name."""
        return reverse(item)
