from django.core.paginator import Paginator, Page


class SearchPaginator(Paginator):
    def _get_page(self, *args, **kwargs):
        return SearchPage(*args, **kwargs)

class SearchPage(Page):
    def __len__(self):
        return self.object_list._extra['size']


def getattr_or_callable(instance, attr, *default):
    try:
        instance = getattr(instance, attr)
        if callable(instance) and not getattr(instance,
                                              'do_not_call_in_templates',
                                              False):
            instance = instance()
        return instance
    except AttributeError:
        if default:
            return default[0]
        raise

def merge(items, overwrite=False, path=()):
    if not items:
        return {}

    if len(items) == 1:
        return items[0]

    if all(isinstance(i, dict) for i in items):
        # Merge dictionaries by recursively merging each key.
        keys = set(chain.from_iterable(six.iterkeys(i) for i in items))
        return dict((k, merge([i[k] for i in items if k in i],
                              overwrite,
                              path + (k,)))
                    for k in keys)
    elif all(isinstance(i, (list, tuple)) for i in items):
        # Merge lists by chaining them together.
        return list(chain.from_iterable(items))
    else:
        if overwrite or all(i == items[0] for i in items):
            # Merge other values by selecting the last one.
            return items[-1]
        raise ValueError("Collision while merging.  Path: %s, values: %s"
                         % (path, items))
