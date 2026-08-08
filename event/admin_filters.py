from admin_auto_filters.filters import AutocompleteFilter


try:
    from admin_auto_filters.filters import AutocompleteFilterMultiple
except ImportError:
    AutocompleteFilterMultiple = AutocompleteFilter


__all__ = ['AutocompleteFilterMultiple']

