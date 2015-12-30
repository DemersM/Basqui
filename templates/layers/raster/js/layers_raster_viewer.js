﻿Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'Ext.window.MessageBox',
    'Ext.window.Window',
    'GeoExt.panel.Map'
]);

Ext.application({
    name: 'Window: raster',
    launch: function() {

      Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
            expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
      }));
  
      map = new OpenLayers.Map('map',
                { projection: new OpenLayers.Projection("EPSG:3857"),
                  numZoomLevels: 20 });
                  
      tiledLayer = new OpenLayers.Layer.XYZ('TMS',
                      "{{ tmsURL }}1.0/raster/${z}/${x}/${y}.png"
                );
                
      map.size = new OpenLayers.Size(1000,800);
      map.addLayer(tiledLayer);
      
      var bounds = new OpenLayers.Bounds.fromArray([-7607286, 5437575, -7543832, 5544003]);
      map.zoomToExtent(bounds);
        
        mappanel = Ext.create('GeoExt.panel.Map', {
            map: map,
            dockedItems: [{
                xtype: 'toolbar',
                dock: 'top',
                items: [{
                    text: 'Current center of the map',
                    handler: function(){
                        var c = GeoExt.panel.Map.guess().map.getCenter();
                        Ext.Msg.alert(this.getText(), c.toString());
                    }
                }]
            }]
        });

        Ext.create('Ext.window.Window', {
            title: "Layer: raster.",
            x: 350,
            y: 120,
            height: 800,
            width: 1000,
            collapsible: true,
            closable: false,
            bodyBorder: false,
            maximizable: true,
            shadowOffset: 6,
            layout: 'fit',
            items: [
                mappanel
            ]
        }).show();
    }
});
