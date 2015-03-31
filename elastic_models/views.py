from django.core.paginator import InvalidPage
from django.views.generic import TemplateView

from oro.search.utils import SearchPaginator

class SearchListView(TemplateView):
    model = None
    paginate_by = None
    paginate_orphans = 0
    paginator_class = SearchPaginator
    page_kwarg = 'page'
    load_models = False
    search_limit = 1000
    
    
    def get(self, request, *args, **kwargs):
        self.search = self.get_search()
        context = self.get_context_data()
        return self.render_to_response(context)
    
    def get_search(self):
        return self.model.search[:self.search_limit]
    
    def paginate_search(self, search, page_size):
        """
        Paginate the search, if needed.
        """
        if not page_size:
            return (None, None, search, False)
        
        paginator = self.get_paginator(search, page_size, 
                                       orphans=self.get_paginate_orphans())
        page_kwarg = self.page_kwarg
        page = self.kwargs.get(page_kwarg) or self.request.GET.get(page_kwarg) or 1
        try:
            page_number = int(page)
        except ValueError:
            if page == 'last':
                page_number = paginator.num_pages
            else:
                raise Http404(_("Page is not 'last', nor can it be converted to an int."))
        try:
            page = paginator.page(page_number)
            return (paginator, page, page.object_list, page.has_other_pages())
        except InvalidPage as e:
            raise Http404(_('Invalid page (%(page_number)s): %(message)s') % {
                                'page_number': page_number,
                                'message': str(e)
            })
    
    def get_paginate_by(self, search):
        """
        Get the number of items to paginate by, or ``None`` for no pagination.
        """
        return self.paginate_by

    def get_paginator(self, search, per_page, orphans=0, **kwargs):
        """
        Return an instance of the paginator for this view.
        """
        return self.paginator_class(search, per_page, orphans=orphans, **kwargs)

    def get_paginate_orphans(self):
        """
        Returns the maximum number of orphans extend the last page by when
        paginating.
        """
        return self.paginate_orphans

    def get_allow_empty(self):
        """
        Returns ``True`` if the view should display empty lists, and ``False``
        if a 404 should be raised instead.
        """
        return self.allow_empty
    
    def get_model_list(self):
        search = self.get_search()
        
        pks = [h.pk for h in search.execute().hits]
        obj_dict = self.model.objects.in_bulk(pks)
        return [obj_dict[pk] for pk in pks]
    
    def get_context_data(self, **kwargs):
        """
        Get the context for this view.
        """
        page_size = self.get_paginate_by(self.search)
        paginator, page, search, is_paginated = self.paginate_search(self.search, page_size)
        
        result = search.execute()
        
        context = {
            'paginator': paginator,
            'page_obj': page,
            'is_paginated': is_paginated,
            'search_result': result,
            'hits': result.hits,
        }
        
        if self.load_models:
            pks = [h.pk for h in result.hits]
            obj_dict = self.model.objects.in_bulk(pks)
            context['object_list'] = [obj_dict[pk] for pk in pks]
        
        context.update(kwargs)
        return super(SearchListView, self).get_context_data(**context)