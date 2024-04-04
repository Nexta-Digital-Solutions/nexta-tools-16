# -*- coding: utf-8 -*-
{
    'name': "Consumible as Service",
    'summary': """Permite crear proyectos y tareas para productos de tipo consumibles
    Añadimos la funcionalidad para que se creen las tareas y los proyectos al confirmar la venta
    Permite marcar abastecimiento de consumibles
    """,

    'description': """
    Permite crear proyectos y tareas para productos de tipo consumibles
    Añadimos la funcionalidad para que se creen las tareas y los proyectos al confirmar la venta
    Permite marcar abastecimiento de consumibles""",
    'author': "NextaDS",
    'website': "https://www.nextads.es",
    'category': '',
    'version': '16.0.0.1',
    'license': "LGPL-3",
    'depends': ['sale',
                'sale_project',
                'project',
                'sale_purchase',
    ],

    'data': [
        'views/product_template_form_view_sale_project_nds.xml',
        'views/product_views_consu_to_purchase.xml',
    ],

    'installable': True
}
