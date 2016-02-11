from __future__ import print_function

from elastic_models.management.commands import IndexCommand

class Command(IndexCommand):
    def handle(self, *args, **options):
        indexes = self.get_indexes(args)

        since = None
        if options['since']:
            since = self.parse_date_time(options['since'])

        limit = None
        if options['limit']:
            limit = int(options['limit'])

        for index in indexes:
            qs = index.get_filtered_queryset(since=since, limit=limit)
            print("Creating mapping for %s.%s" % (index.model.__name__, index.name))
            index.put_mapping()
            print("Indexing %d %s objects" % (qs.count(), index.model.__name__))
            index.index_queryset(qs)
