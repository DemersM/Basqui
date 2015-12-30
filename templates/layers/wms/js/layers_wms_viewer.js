Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'Ext.window.MessageBox',
    'Ext.window.Window',
    'GeoExt.panel.Map'
]);

Ext.application({
    name: 'Window: {{ wms.alias }}',
    launch: function() {

      Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
            expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
      }));
      source = new OpenLayers.Projection("EPSG:4326");
      dest = new OpenLayers.Projection("EPSG:{{ wms.srs }}");

      map = new OpenLayers.Map('map',
                { projection: new OpenLayers.Projection("EPSG:3857") });

      {{ wms.alias }} = new OpenLayers.Layer.WMS( "{{ wms.alias }",
                  "{{ wms.url }}", {layers: [{% for wmsLayer in wmsLayers_in_use %}'{{ wmsLayer.layer_name }}',{% endfor %}], isBaseLayer: true},
                                   {projection: "EPSG:{{ wms.srs }}"});
      map.addLayer({{ wms.alias }});

      map.size = new OpenLayers.Size(1000,800);
      var bounds = new OpenLayers.Bounds{{ bounds }};

      map.zoomToExtent(bounds.transform(source,dest));

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
          title: "{{ wms.alias }}",
          x: 400,
          y: 100,
          height: 800,
          width: 1000,
          collapsible: true,
          closable: false,
          bodyBorder: false,
          shadowOffset: 6,
          layout: 'fit',
          items: [
              mappanel
          ]
      }).show();
  }
});
