from __future__ import print_function

from oro.search.management.commands import IndexCommand

class Command(IndexCommand):
    def handle(self, *args, **options):
        models = self.get_models(args)

        since = None
        if options['since']:
            since = self.parse_date_time(options['since'])

        limit = None
        if options['limit']:
            limit = int(options['limit'])

        for model in models:
            search = model._search_meta()
            qs = search.get_qs(since=since, limit=limit)
            print "Indexing %d %s objects" % (qs.count(), model.__name__)
            search.index_qs(qs)
