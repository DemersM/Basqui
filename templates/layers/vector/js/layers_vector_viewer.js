OpenLayers.Control.Click = OpenLayers.Class(
    OpenLayers.Control, {
        defaultHandlerOptions: {
           'single' : true,
           'double' : false,
           'pixelTolerance' : 0,
           'stopSingle' : false,
           'stopDouble' : false
        },

        initialize: function(options) {
            this.handlerOptions = OpenLayers.Util.extend(
                {}, this.defaultHandlerOptions);
            OpenLayers.Control.prototype.initialize.apply(
                this, arguments);
            this.handler = new OpenLayers.Handler.Click(
                this, {'click' : this.trigger}, this.handlerOptions);
        },
        trigger: function(e) {
            var coord = map.getLonLatFromViewPortPx(e.xy);
            var zoomLevel = map.getZoom();
            Ext.Ajax.request({
                    url: '/basqui/layer/shapefile/selectFeature',
                    method: 'POST',
                    params: {
                              'layer_id': {{ shapefile.pk }},
                              'latitude': coord.lat,
                              'longitude': coord.lon
                            },
                    success: function(r){
                              geoJsonToVectorLayer(Ext.decode(r.responseText).geojson);
                            }
                    });
        }
    }
);

OpenLayers.Control.Hover = OpenLayers.Class(OpenLayers.Control, {
    defaultHandlerOptions: {
        'delay': 200,
        'pixelTolerance': null,
        'stopMove': false
    },

    initialize: function(options) {
        this.handlerOptions = OpenLayers.Util.extend(
            {}, this.defaultHandlerOptions
        );
        OpenLayers.Control.prototype.initialize.apply(
            this, arguments
        );
        this.handler = new OpenLayers.Handler.Hover(
            this,
            {'pause': this.onPause, 'move': this.onMove},
            this.handlerOptions
        );
    },
    onPause: function(e) {
        var coord = map.getLonLatFromViewPortPx(e.xy);
        var zoomLevel = map.getZoom();
        var request = OpenLayers.Request.GET({
              url : "/basqui/layer/shapefile/hoverFeature",
              params : {shapefile_id : {{ shapefile.id }},
              latitude : coord.lat,
              longitude : coord.lon,
                       },
        callback : this.handleResponse
    });
    },
    handleResponse: function(r) {
        if (r.status != 200) {
            alert("Server returned a "+r.status+" error");
            return;
        };
        if (r.responseText != '') {
            Ext.getCmp('attrTable').update(r.responseText);
        };
    },
});

Ext.require([
    'Ext.state.Manager',
    'Ext.state.CookieProvider',
    'Ext.window.MessageBox',
    'Ext.window.Window',
    'GeoExt.panel.Map'
]);

Ext.state.Manager.setProvider(Ext.create('Ext.state.CookieProvider', {
      expires: new Date(new Date().getTime()+(1000*60*60*24*7)) //7 days from now
}));

var map = new OpenLayers.Map('map',
          { projection: new OpenLayers.Projection("EPSG:3857"),
            numZoomLevels: 20,
            });

var blank = new OpenLayers.Layer("Blank", {isBaseLayer: true});

var tiledLayer = new OpenLayers.Layer.CustomXYZ('{{ shapefile.name }}',
                "{{ tmsURL }}1.0/layer/{{ shapefile.id }}/${z}/${x}/${y}.png", {isBaseLayer: false});

var tmsLayer = new OpenLayers.Layer.TMS(
    "Gouvernement du Quebec",
    "http://pregeoegl.msp.gouv.qc.ca/cgi-wms/mapcache.fcgi/tms/",
   { layername: 'carte_gouv_qc_public@EPSG_3857', 
     type: "png", 
     serviceVersion:"1.0.0",
     gutter:0,
     buffer:0,
     isBaseLayer:true,
     tileOrigin: new OpenLayers.LonLat(-20037508.342789,-20037508.342789),
     numZoomLevels: null,
     maxZoomLevel: 16,
     minZoomLevel: 4,     
     zoomOffset:0,
     animate: true,
     visibility: true,
     transitionEffect: 'null',
     units:"m",
     maxExtent: new OpenLayers.Bounds(-20037508.342789,-20037508.342789,20037508.342789,20037508.342789),
     projection: new OpenLayers.Projection("EPSG:3857".toUpperCase()),
     sphericalMercator: true
     }
  ); 


var clickListeners = {nofeatureclick : function(e){
    click.activate();
  },
  featureclick: function(e){
    click.deactivate();
    vectorLayer.destroyFeatures(vectorLayer.getFeaturesByAttribute('feat_id', e.feature.attributes.feat_id));
  }
}


var vectorLayer = new OpenLayers.Layer.Vector('Vector');
vectorLayer.events.on(clickListeners);

var tempLayer = new OpenLayers.Layer.Vector('Temp'); 
map.addLayers([blank, tmsLayer, tiledLayer, vectorLayer, tempLayer, ]);

map.size = new OpenLayers.Size(1125,745);
var bounds = new OpenLayers.Bounds.fromArray({{ bounds }});
map.zoomToExtent(bounds);

map.addControl(new OpenLayers.Control.LayerSwitcher());

var modifyControl = new OpenLayers.Control.ModifyFeature(vectorLayer, {bySegment: false, createVertices: false});
var drawCtrl = new OpenLayers.Control.DrawFeature(vectorLayer, OpenLayers.Handler.{% if shapefile.geom_type == "LineString" %}Path{% else %}{{ shapefile.geom_type }}{% endif %});
var click = new OpenLayers.Control.Click();
var splitCtrl = new OpenLayers.Control.DrawFeature(tempLayer, OpenLayers.Handler.Path);
var eraseCtrl = new OpenLayers.Control.DrawFeature(tempLayer, OpenLayers.Handler.Polygon);
var hover = new OpenLayers.Control.Hover();
map.addControls([click, hover, modifyControl, splitCtrl, eraseCtrl, drawCtrl]);

console.log(map)

hover.activate();

var toggleGroup = "Edit feature tools";
var geoJsonFormat = new OpenLayers.Format.GeoJSON();

var geoExtPanel = Ext.create('GeoExt.panel.Map', {
    id: 'geoExtPanel',
    map: map,
    border: 0,
    dockedItems: [{
        id: 'toolbar',
        xtype: 'toolbar',
        dock: 'top',
        items: [
            {
              text: 'Current center of the map',
              handler: function(){
                          var c = GeoExt.panel.Map.guess().map.getCenter();
                          Ext.Msg.alert(this.getText(), c.toString());
                       }
            },
            {
              text: 'Simplify layer',
              handler: function(){
                  Ext.MessageBox.prompt('Ratio', 'Enter a ratio (ex: 0.5)', function(btn, ratio){
                      if (btn == 'ok') {
                        Ext.Ajax.request({
                           url: '/basqui/layer/shapefile/simplify',
                           method: 'POST',
                           params: {'id': {{ shapefile.pk }},
                                    'ratio': ratio },
                           success: function(r){
                                      tiledLayer.redraw(true);
                                    }
                        });
                      }
                  });
              }
            },
            {
              id: 'editBtn',
              text: 'Start Editing',
              style: { width: '75px' },
              xtype: 'button',
              toggleGroup: 'custom1',
              toggleHandler: function(btn, pressed) {
                if (pressed){
                  vectorLayer.events.un(clickListeners);
                  btn.setText('Stop Editing');
                  modifyControl.activate();
                  editPanel.show();
                  click.deactivate();
                } else {
                  btn.setText('Start Editing');
                  vectorLayer.events.on(clickListeners);
                  modifyControl.deactivate();
                  editPanel.hide();
                  click.activate();
                }
              }
            },
            {
              text: 'Save',
              xtype: 'button',
              handler: function(){
                  modifyControl.deactivate();
                  Ext.Ajax.request({
                    url: '/basqui/layer/shapefile/saveEdits',
                    method: 'POST',
                    params: {
                              'layer_id': {{ shapefile.pk }},
                              'feat_id': vectorLayer.feat_id,
                              'feature': vectorLayerToGeoJson()
                            },
                    success: function(r){
                              modifyControl.activate();
                              tiledLayer.redraw(true);
                            }
                    });
                }
            },
            {
              id: 'cancelBtn', 
              text: 'Cancel',
              xtype: 'button',
              handler: function(){
                Ext.getCmp('editBtn').toggle(false);
                vectorLayer.destroyFeatures();
              }
            }
        ]
    }]
});

var attrPanel = Ext.create('Ext.panel.Panel', {
  id: 'attrTable',
  border: 0,
  overflowX: 'auto',
  overflowY: 'auto',
  dockedItems: [{
    xtype: 'toolbar',
    dock: 'top',
    items: [
      {
        text: 'Save',
        handler: function(){
            var formJson = $('#featureAttributesForm').serializeObject();
            if (jQuery.isEmptyObject(formJson) != true) {
              $.ajax({
                  type: "POST",
                  url: "/basqui/layer/shapefile/attributesTable/{{ shapefile.pk }}/update/",
                  data: formJson, dataType: "json",
                  success: function(r) {
                              if(r['error']) {
                                   $("#saved").empty();
                                   $("#error").text(r['error']);
                              }
                              else {
                                   $("#error").empty();
                                   $("#saved").text(r['saved']);
                                   $('#featureAttributesForm').find('input').each(function() {
                                        this['value'] = r['data'][this['name']]
                                   });
                              }
                            }
                   });
          } else {
            return false;
          }
        }
      },
      {
        text: 'Freeze',
        toggleGroup: 'custom',
        toggleHandler: function(btn, pressed) {
          if(pressed){
            btn.setText('Release');
            hover.deactivate();
          } else {
            btn.setText('Freeze');
            hover.activate();
          }
        }
      }
    ]
  }]
});

var mapContainer = Ext.create('Ext.panel.Panel', {
    title: "Layer: {{ shapefile }} | Click on feature to edit.",
    height: 745,
    width: 1125,
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
              editPanel.doComponentLayout();
          }
      }],
    renderTo: 'mapContainer'
}).show();

var attrTableContainer = Ext.create('Ext.panel.Panel', {
    title: "Layer: {{ shapefile }} | Attributes Table.",
    height: 400,
    width: 400,
    layout: 'fit',
    autoScroll: true,
    autoDestroy: false,
    bodyStyle:{"background-color":"#fff"},
    items: [
     attrPanel
    ],
    tools: [{
          type: 'maximize',
          handler: function() {
              var content = attrTableContainer.getComponent(0);
              attrTableContainer.remove(content);
              attrTableContainer.hide();
              attrWin.add(content);
              attrWin.show();
          }
      }],
    renderTo: 'attrTableContainer'
}).show();

var mapWin = Ext.create('Ext.window.Window', {
  title: "Layer: {{ shapefile }} | Click on feature to edit.",
  x: 350,
  y: 175,
  height: 745,
  width: 1125,
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
          mapContainer.add(content);
          mapContainer.show();
          editPanel.doComponentLayout();
      },
      resize: function() {
        editPanel.doComponentLayout();
      }
  },
  renderTo: Ext.getBody()
});

var attrWin = Ext.create('Ext.window.Window', {
  title: "Layer: {{ shapefile }} | Attributes Table.",
  x: 1500,
  y: 175,
  height: 400,
  width: 400,
  layout: 'fit',
  bodyStyle:{"background-color":"#fff"},
  collapsible: true,
  autoScroll: true,
  bodyBorder: false,
  shadowOffset: 6,
  autoDestroy: false,
  closeAction: 'hide',
  listeners: {
      close: function() {
          var content = attrWin.getComponent(0);
          attrWin.remove(content);
          attrTableContainer.add(content);
          attrTableContainer.show();
      }
  },
  renderTo: Ext.getBody()
});

var editPanel = Ext.create('Ext.panel.Panel', {
    id: 'editPanel',
    renderTo: 'geoExtPanel',
    height: 30,
    border: 0,
    bodyStyle: {background:'none'},
    style: {position:'absolute', top:'35px'},
    hidden: true,
});

var drawBtn = Ext.create('Ext.Button', {
    id: 'drawBtn',
    text: 'Draw',
    renderTo: 'editPanel',
    style: {position:'absolute', width:'60px', top:'0', right:'192px'},
    toggleGroup: 'toggleGroup',
    toggleHandler: function(btn, pressed) {
      if (pressed){
        drawCtrl.activate();
        vectorLayer.events.on({sketchcomplete : function(){ drawCtrl.deactivate()}});
      } else {
        drawCtrl.deactivate();
      }
    }
}).show();

var splitBtn = Ext.create('Ext.Button', {
    id: 'splitBtn',
    text: 'Split',
    renderTo: 'editPanel',
    style: {position:'absolute', width:'60px', top:'0', right:'128px'},
    toggleGroup: 'toggleGroup',
    toggleHandler: function(btn, pressed) {
      if (pressed){
        splitCtrl.activate();
      } else {
          splitCtrl.deactivate();
      }
    }
}).show();

var eraseBtn = Ext.create('Ext.Button', {
    id: 'eraseBtn',
    text: 'Erase',
    renderTo: 'editPanel',
    style: {position:'absolute', width:'60px', top:'0', right:'66px'},
    toggleGroup: 'toggleGroup',
    toggleHandler: function(btn, pressed) {
      if (pressed){
        eraseCtrl.activate();
      } else {
          eraseCtrl.deactivate();
      }
    }
}).show();

var unionBtn = Ext.create('Ext.Button', {
    id: 'unionBtn',
    text: 'Union',
    renderTo: 'editPanel',
    style: {position:'absolute', width:'60px', top:'0', right:'4px'},
    toggleGroup: 'toggleGroup',
    toggleHandler: function(btn, pressed) {
      if (pressed){
        Ext.Ajax.request({
          url: '/basqui/layer/shapefile/union',
          method: 'POST',
          params: {
                    'layer_id': {{ shapefile.pk }},
                    'feature': vectorLayerToGeoJson()
                  },
          success: function(r){
                      vectorLayer.removeAllFeatures();
                      geoJsonToVectorLayer(Ext.decode(r.responseText));
                      unionBtn.toggle(false);
                   }
        });
      }
    }
}).show();

splitCtrl.events.on({featureadded : function(){ 
  Ext.Ajax.request({
    url: '/basqui/layer/shapefile/split',
    method: 'POST',
    params: {
              'layer_id': {{ shapefile.pk }},
              'feature': vectorLayerToGeoJson(),
              'blade': geoJsonFormat.write(tempLayer.features[0].geometry)
            },
    success: function(r){
                tempLayer.destroyFeatures();
                vectorLayer.destroyFeatures();
                geoJsonToVectorLayer(Ext.decode(r.responseText));
                splitBtn.toggle(false);
             }
    });
}});

eraseCtrl.events.on({featureadded : function(){ 
  Ext.Ajax.request({
    url: '/basqui/layer/shapefile/erase',
    method: 'POST',
    params: {
              'layer_id': {{ shapefile.pk }},
              'feature': vectorLayerToGeoJson(),
              'mask': geoJsonFormat.write(tempLayer.features[0].geometry)
            },
    success: function(r){
                tempLayer.destroyFeatures();
                vectorLayer.destroyFeatures();
                geoJsonToVectorLayer(Ext.decode(r.responseText));
                eraseBtn.toggle(false);
             }
    });
}});

function vectorLayerToGeoJson(){
  console.log('vectorLayer:')
  console.log(vectorLayer)
  outputFeature = new OpenLayers.Layer.Vector();
  var newArr = [];
  var types = {};
  for (var i = 0, j = vectorLayer.features.length; i < j; i++) {
      var cur = vectorLayer.features[i];
      if (!(cur.attributes['feat_id'] in types)) {
          types[cur.attributes['feat_id']] = {feat_id: cur.attributes['feat_id'], geometries: []};
          newArr.push(types[cur.attributes['feat_id']]);
      }
      types[cur.attributes['feat_id']].geometries.push(cur.geometry);
  }
  console.log('newArray:')
  console.log(newArr)
  for (var i = 0; i < newArr.length; i++){
    feature = new OpenLayers.Feature.Vector(new OpenLayers.Geometry.Multi{{ shapefile.geom_type }}, {'feat_id' :newArr[i].feat_id});
    feature.geometry.addComponents(newArr[i].geometries);
    outputFeature.addFeatures(feature)
  }
  console.log('outputFeature:')
  console.log(outputFeature)
  return geoJsonFormat.write(outputFeature.features);
}

function geoJsonToVectorLayer(geoJsonInput){
  var inputFeatures = geoJsonFormat.read(geoJsonInput)
  console.log('inputFeatures:')
  console.log(inputFeatures)
    for (var i = 0; i < inputFeatures.length; i++){
      if (inputFeatures[i].geometry) {
        for (var j = 0; j < inputFeatures[i].geometry.components.length; j++){
          vectorLayer.addFeatures(new OpenLayers.Feature.Vector(inputFeatures[i].geometry.components[j], inputFeatures[i].attributes ));
        }
      } else {
          vectorLayer.addFeatures(inputFeatures[i]);
      }
    }
    console.log('vectorLayer:')
    console.log(vectorLayer)
}

$.fn.serializeObject = function(){
    var o = {};
    var a = this.serializeArray();
    $.each(a, function() {
        if (o[this.name] !== undefined) {
            if (!o[this.name].push) {
                o[this.name] = [o[this.name]];
            }
            o[this.name].push(this.value || '');
        } else {
            o[this.name] = this.value || '';
        }
    });
    return o;
};
