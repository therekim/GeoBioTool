def classFactory(iface):
    from .geobiotool import GeoBioToolPlugin
    return GeoBioToolPlugin(iface)