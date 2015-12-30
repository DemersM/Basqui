initLayerMapOptionsFormset();

function formatMarker(marker) {
  if (!marker.id) { return marker.text; }
  var $marker = $(
       '<span><img src="/media/markers/maki/' + marker.text.toLowerCase() + '.svg" class="img-flag" /> ' + marker.text.charAt(0).toUpperCase() + marker.text.slice(1) + '</span>'
  );
  return $marker;
}

function initLayerMapOptionsFormset(){
  checkLayersOrder();
  $( ".table.sortable  tbody" ).sortable({
        stop: function(){
            checkLayersOrder();
        }
  });
  $("form#layerMapOptionsFormset :input").each(function(){
    $(this).change(function() {
      Ext.Ajax.request({
        url: "{% url 'maps:saveLayerMapOptions' map.pk %}",
        method: "POST",
        form: "layerMapOptionsFormset",
        success: function(r){
                     Ext.get("layerMapOptions").update(r.responseText);
                     initLayerMapOptionsFormset()
                     tiledLayer.redraw(true)
                 }
      });
    });
  });
}

function checkLayersOrder(){
  var checks = new Array();
  $("input[class='layer_id']").each(function(index, value) {
        checks.push($(value).val());
  });
  $("#layersOrder").val(checks).trigger('change');
}

function initLayerStyleFormset(layer_id) {
  checkLayerStyleOrder(layer_id);
  $( "#layerStyleTabs_" + layer_id).sortable({
        stop: function(){
            checkLayerStyleOrder(layer_id);
        }
  });
  $(".spectrum").each(function (i, elem) { $(elem).spectrum()});
  $(".markerSelect").each(function (i, elem) { $(elem).select2({
          formatResult: formatMarker,
          formatSelection: formatMarker
      });
  });
  $(".layerStyleClose_"+layer_id).click(function () {
      var tabContentId = $(this).parent().attr("href");
      $(this).parent().parent().remove();
      $(tabContentId).hide();
      $('#layerStyleTabs_' + layer_id + ' a:first').tab('show');
      $(tabContentId).find('.hiddenDiv input[type=checkbox]').prop('checked', true);
  });
}

function initLayerLabelFormset(layer_id) {
  checkLayerLabelOrder(layer_id);
  $( "#layerLabelTabs_" + layer_id).sortable({
        create:function(){
            checkLayerLabelOrder(layer_id);
        },
        stop: function(){
            checkLayerLabelOrder(layer_id);
        }
  });
  $(".spectrum").each(function (i, elem) { $(elem).spectrum()});
  $(".layerLabelClose_"+layer_id).click(function () {
      var tabContentId = $(this).parent().attr("href");
      $(this).parent().parent().remove();
      $(tabContentId).hide();
      $('#layerLabelTabs_' + layer_id + ' a:first').tab('show');
      $(tabContentId).find('.hiddenDiv input[type=checkbox]').prop('checked', true);
  });
}

function checkLayerStyleOrder(layer_id){
  var checks = new Array();
  $(".layerStyle_li_" + layer_id).each(function(index, value) {
        checks.push($(value).attr("layerStyle_id"));
  });
  $("#layerStyleOrder_" + layer_id).val(checks);
}

function checkLayerLabelOrder(layer_id){
  var checks = new Array();
  $(".layerLabel_li_" + layer_id).each(function(index, value) {
        checks.push($(value).attr("layerLabel_id"));
  });
  $("#layerLabelOrder_" + layer_id).val(checks);
}

var map = new OpenLayers.Map('mappanel',
  { projection: new OpenLayers.Projection("EPSG:3857")});

var apiKey = "AqTGBsziZHIJYYxgivLBf0hVdrAk9mWO5cQcb8Yux8sW5M8c8opEC2lZqKR1ZZXf";
var fromProjection = new OpenLayers.Projection("EPSG:4326");
var toProjection   = new OpenLayers.Projection("EPSG:3857");

map.addControl(new OpenLayers.Control.LayerSwitcher());

var blank = new OpenLayers.Layer("Blank", {isBaseLayer: true});

var osm = new OpenLayers.Layer.OSM("OSM"
);
var road = new OpenLayers.Layer.Bing({
    name: "Road",
    key: apiKey,
    type: "Road",
});
var hybrid = new OpenLayers.Layer.Bing({
    name: "Hybrid",
    key: apiKey,
    type: "AerialWithLabels",
});

var aerial = new OpenLayers.Layer.Bing({
    name: "Aerial",
    key: apiKey,
    type: "Aerial"
});

var tiledLayer = new OpenLayers.Layer.CustomXYZ('{{ map.name }}',
            "{{ tmsURL }}", {serverResolutions: hybrid.serverResolutions, isBaseLayer: false, transitionEffect: null}
      );
map.addLayers([tiledLayer, blank, osm, road, hybrid, aerial]);

Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'Ext.window.MessageBox',
    'Ext.window.Window',
    'GeoExt.panel.Map',
    'Ext.Ajax.request',
]);

Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
      expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
}));

var geoExtPanel = Ext.create('GeoExt.panel.Map', {
    id: 'geoExtPanel',
    map: map,
    center: new OpenLayers.LonLat({{ map.center_long }}, {{ map.center_lat }}).transform(fromProjection , toProjection),
    zoom: {{ map.zoom_level }},
    border: 0,
    dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [
          {
            text: "Fix",
            handler: function () {
              Ext.Ajax.request({
                  url: "{% url 'maps:fixMap' %}",
                  method: 'POST',
                  params: {'map_id': {{ map.id }}, 'center_lat':map.center.lat, 'center_lon':map.center.lon, 'zoom':map.zoom, 'map_height':mapWin.getHeight(), 'map_width':mapWin.getWidth()},
                  success: function(r) {
                                Ext.get("mapOptions").update(r.responseText);
                  }
              });
            }
          }
        ]
    }]
});

var mapContainer = Ext.create('Ext.panel.Panel', {
    title: "Map: {{ map.name }}",
    height: {{ map.map_height }},
    width: {{ map.map_width }},
    maxWidth: 1110,
    layout: 'fit',
    autoDestroy: false,
    bodyStyle:{"background-color":"#fff"},
    items: [
     geoExtPanel
    ],
    tools: [{
          type: 'maximize',
          handler: function() {
              var content = mapContainer.getComponent(0);
              mapContainer.remove(content);
              mapContainer.hide();
              mapWin.add(content);
              mapWin.show();
          }
      }],
    renderTo: 'mapContainer'
}).show();

var mapWin = Ext.create('Ext.window.Window', {
  title: "Map: {{ map.name }}",
  x: 350,
  y: 175,
  height: {{ map.map_height }},
  width: {{ map.map_width }},
  layout: 'fit',
  collapsible: true,
  bodyBorder: false,
  shadowOffset: 6,
  autoDestroy: false,
  closeAction: 'hide',
  listeners: {
      close: function() {
          var content = mapWin.getComponent(0);
          mapWin.remove(content);
          mapContainer.setSize(mapWin.getSize());
          mapContainer.add(content);
          mapContainer.show();
      },
  },
  renderTo: Ext.getBody()
});

var x_offset = y_offset = 0;

window.layerStyleWin = function(layer_id, layer_name){
  var layerStyleWin = Ext.get("layerStyleWin_" + layer_id)
  if (!layerStyleWin){
    var layerStyleWindow = Ext.create('Ext.window.Window', {
      title: layer_name + ": Styling options",
      id: "layerStyleWin_" + layer_id,
      x: 175 + x_offset,
      y: 175 + y_offset,
      height: 650,
      width: 500,
      minWidth: 500,
      layout: 'fit',
      collapsible: true,
      bodyStyle: 'background:#fff; padding:10px;',
      bodyBorder: false,
      autoScroll: true,
      shadowOffset: 6,
      closeAction: 'destroy',
      dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [
          {
            text: "Save",
            handler: function() { 
              layerStyle(layer_id); 
            }
          }
        ]
      }],
      listeners: {
        afterrender: function(){
              layerStyle(layer_id);
              x_offset += 10;
              y_offset += 30;
        }
      },
      renderTo: Ext.getBody()
    }).show();
   }
}

window.layerLabelWin = function(layer_id, layer_name){
  var layerLabelWin = Ext.get("layerLabelWin_" + layer_id)
  if (!layerLabelWin){
    var layerLabelWindow = Ext.create('Ext.window.Window', {
      title: layer_name + ": Labeling options",
      id: "layerLabelWin_" + layer_id,
      x: 175 + x_offset,
      y: 175 + y_offset,
      height: 650,
      width: 500,
      minWidth: 500,
      layout: 'fit',
      collapsible: true,
      bodyStyle: 'background:#fff; padding:10px;',
      bodyBorder: false,
      autoScroll: true,
      shadowOffset: 6,
      closeAction: 'destroy',
      dockedItems: [{
        xtype: 'toolbar',
        dock: 'top',
        items: [
          {
            text: "Save",
            handler: function() { 
              layerLabel(layer_id);
            }
          }
        ]
      }],
      listeners: {
        afterrender: function(){
              layerLabel(layer_id);
              x_offset += 10;
              y_offset += 30;
        }
      },
      renderTo: Ext.getBody()
    }).show();
   }
}

window.layerStyle = function(layer_id){
   Ext.Ajax.request({
        url: "{% url 'maps:setLayerStyle' %}",
        method: "POST",
        params: {'layer_id' : layer_id },
        form: "layerStyleForm_" + layer_id,
        success : function(r){
                      var currentWin = Ext.getCmp("layerStyleWin_" + layer_id);
                      currentWin.update(Ext.decode(r.responseText).html);
                      initLayerStyleFormset(layer_id);
                      if (Ext.decode(r.responseText).save == 'success'){
                        tiledLayer.redraw(true);
                      }
                  }
   });
}

window.layerLabel = function(layer_id){
   Ext.Ajax.request({
        url: "{% url 'maps:setLayerLabel' %}",
        method: "POST",
        params: {'layer_id' : layer_id },
        form: "layerLabelForm_" + layer_id,
        success : function(r){
                      var currentWin = Ext.getCmp("layerLabelWin_" + layer_id);
                      currentWin.update(Ext.decode(r.responseText).html);
                      initLayerLabelFormset(layer_id);
                      if (Ext.decode(r.responseText).save == 'success'){
                        tiledLayer.redraw(true);
                      }
                  }
   });
}

window.saveMapOptions = function(map_id){
    Ext.Ajax.request({
      url: "{% url 'maps:saveMapOptions' %}",
      method: "POST",
      params: {'map_id' : map_id },
      form: "mapOptionsForm",
      success: function(r){
                   Ext.get("mapOptionsForms").update(r.responseText);
                   initMapOptionsForms();
                   tiledLayer.redraw(true)
               }
    });
}

window.selectLayers = function(){
    var selectLayersWin = Ext.get("selectLayersWin")
    if (!selectLayersWin){
      Ext.Ajax.request({
        url: "{% url 'maps:selectLayers' map.pk %}",
        method: "POST",
        success : function(r){
                      eval(Ext.decode(r.responseText));
                  }
       });
    }
}