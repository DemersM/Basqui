var map = new OpenLayers.Map('map',{ projection: new OpenLayers.Projection("EPSG:3857") });

var osm = new OpenLayers.Layer.OSM("OSM");
var bbox = new OpenLayers.Layer.Vector("Bbox");
map.addLayers([osm, bbox]);

var drawCtrl = new OpenLayers.Control.DrawFeature(bbox, OpenLayers.Handler.RegularPolygon, {
          handlerOptions: {
            sides: 4,
            snapAngle: 90,
            irregular: true,
            persist: true
          }
});
drawCtrl.handler.callbacks.done = endDraw;

var transform = new OpenLayers.Control.TransformFeature(bbox, {rotate:false, irregular:true});

transform.events.on({
    "transformcomplete": displayCoordinates
});


map.addControls([drawCtrl, transform]);

Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'GeoExt.panel.Map',
    'Ext.Ajax.request',
]);

Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
      expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
}));

var geoExtPanel = Ext.create('GeoExt.panel.Map', {
    id: 'geoExtPanel',
    map: map,
    border: 0,
    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [
          {
            text: "Draw BBox",
            handler: function () {
                        transform.deactivate();
                        bbox.destroyFeatures();
                        drawCtrl.activate();
            }
          },{
            text: "Use layer's extent",
            handler: function () {
                        alert('yo');
            }
          },{
            text: "Copy extent to clipboard",
            handler: function () {
            alert('yo');
            }
          }]
     }]
});

var mapContainer = Ext.create('Ext.panel.Panel', {
    title: "Bounding box used by Overpass API",
    height: 600,
    width: 600,
    layout: 'fit',
    bodyStyle:{"background-color":"#fff"},
    items: [
     geoExtPanel
    ],
    renderTo: 'mapContainer'
}).show();

function endDraw(geom) {
  var bounds = geom.getBounds();
  var feature = new OpenLayers.Feature.Vector(bounds.toGeometry());
  console.log(feature)
  bbox.removeAllFeatures();
  bbox.addFeatures(feature);
  transform.unsetFeature();
  transform.setFeature(feature);
  drawCtrl.deactivate();
  displayCoordinates();
}

function displayCoordinates() {
  var extent = bbox.getDataExtent().transform(new OpenLayers.Projection("EPSG:3857"),new OpenLayers.Projection("EPSG:4326"));
  $("#id_maxY").val(extent.top);
  $("#id_minX").val(extent.left);
  $("#id_maxX").val(extent.right);
  $("#id_minY").val(extent.bottom);
}
$("#bbox-div :input").each(function(){
    $(this).change(function() {
      var minX = Math.min($("#id_minX").val(),$("#id_maxX").val());
      var minY = Math.min($("#id_minY").val(),$("#id_maxY").val());
      var maxX = Math.max($("#id_minX").val(),$("#id_maxX").val());
      var maxY = Math.max($("#id_minY").val(),$("#id_maxY").val());
      var values = [minX, minY, maxX, maxY];
      //var values = [$("#id_minX").val(),$("#id_minY").val(), $("#id_maxX").val(),$("#id_maxY").val()];
      var bounds = new OpenLayers.Bounds.fromArray(values);
      if (bounds.getSize().w != 0 && bounds.getSize().h != 0) {
        var feature = new OpenLayers.Feature.Vector(bounds.toGeometry());
        bbox.removeAllFeatures();
        bbox.addFeatures(feature);
        transform.unsetFeature();
        transform.setFeature(feature);
        displayCoordinates();
      }
    });
});
