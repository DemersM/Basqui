OpenLayers.Layer.CustomXYZ = OpenLayers.Class(OpenLayers.Layer.XYZ, {
  getURL: function () {
    var url = OpenLayers.Layer.XYZ.prototype.getURL.apply(this, arguments);
    return url + '?time='+ new Date().getTime();
  }
});