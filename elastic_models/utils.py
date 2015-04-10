from django.core.paginator import Paginator, Page


class SearchPaginator(Paginator):
    def _get_page(self, *args, **kwargs):
        return SearchPage(*args, **kwargs)

class SearchPage(Page):
    def __len__(self):
        return self.object_list._extra['size']
