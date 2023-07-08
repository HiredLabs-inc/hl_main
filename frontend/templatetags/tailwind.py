from django import template

register = template.Library()


def get_tw_button_classes(variant):
    base_classes = """
                    text-base py-[9px] 
                    transition-all 
                    active:scale-90 
                    px-5 
                    rounded-lg 
                    inline-flex 
                    items-center 
                    justify-center 
                    hover:brightness-110
                    relative"""

    tailwind_button_classes = {
        "primary": "bg-brand-500 hover:bg-brand-700 text-white ",
        "secondary": "bg-gray-500 hover:bg-gray-700 text-white ",
        "success": "bg-green-500 hover:bg-green-700 text-white ",
        "danger": "bg-red-500 hover:bg-red-700 text-white ",
        "warning": "bg-yellow-500 hover:bg-yellow-700 text-white ",
        "info": "bg-teal-500 hover:bg-teal-700 text-white ",
        "light": "bg-gray-100 hover:bg-gray-300 text-gray-800 ",
        "dark": "bg-gray-700 hover:bg-gray-900 text-white ",
        "outline-primary": "bg-transparent hover:bg-brand-500 text-brand-700 hover:text-white border-2 border-brand-500 hover:border-transparent ",
        "outline-secondary": "bg-transparent hover:bg-gray-500 text-gray-700 hover:text-white border-2 border-gray-500 hover:border-transparent ",
        "outline-success": "bg-transparent hover:bg-green-500 text-green-700 hover:text-white border-2 border-green-500 hover:border-transparent ",
        "outline-danger": "bg-transparent hover:bg-red-500 text-red-700 hover:text-white border-2 border-red-500 hover:border-transparent ",
        "outline-warning": "bg-transparent hover:bg-yellow-500 text-yellow-700 hover:text-white border-2 border-yellow-500 hover:border-transparent ",
        "outline-info": "bg-transparent hover:bg-teal-500 text-teal-700 hover:text-white border-2 border-teal-500 hover:border-transparent ",
        "outline-light": "bg-transparent hover:bg-gray-100 text-gray-700 hover:text-white border-2 border-gray-100 hover:border-transparent ",
        "outline-dark": "bg-transparent hover:bg-gray-700 text-gray-700 hover:text-white border-2 border-gray-700 hover:border-transparent ",
        "link": "bg-transparent hover:bg-transparent text-brand-500 hover:text-brand-700 border-2 border-transparent ",
    }
    return f"{base_classes} {tailwind_button_classes[variant or 'primary']}"


@register.simple_tag
def tw_button(variant):
    return get_tw_button_classes(variant)


@register.simple_tag
def tw_th(mobile_hide=False):
    return (
        "text-left p-3 text-sm font-semibold tracking-wide "
        f"{'hidden' if mobile_hide else 'flex'} md:table-cell"
    )


@register.simple_tag
def tw_tr():
    return "odd:bg-gray-100 border-t border-gray-200"


@register.simple_tag
def tw_td():
    return (
        "md:before:content-none before:content-[attr(data-cell)':_'] before:capitalize before:font-bold "
        "grid grid-cols-[12ch_auto] md:table-cell p-2 text-sm text-gray-700"
    )
