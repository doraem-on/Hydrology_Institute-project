/* Event layers: flood candidates, SAR slope-change candidates, NDTI.
 * Import verified roi geometry. Configure dates/orbit and calibrate thresholds
 * on separate labelled events. Result names deliberately describe proxies.
 */
if (typeof roi === 'undefined') { throw new Error('Import a verified roi geometry.'); }
var CONFIG = {
  beforeStart: '2024-06-01', beforeEnd: '2024-07-01',
  afterStart: '2024-07-01', afterEnd: '2024-07-13',
  relativeOrbit: null, pass: 'DESCENDING', polarization: 'VH',
  floodDropDb: 3, floodMaximumDb: -15, landslideChangeDb: 4,
  minimumConnectedPixels: 8, exportCrs: null
};
if (CONFIG.relativeOrbit === null || CONFIG.exportCrs === null) {
  throw new Error('Set relativeOrbit and a suitable local metric exportCrs.');
}
if (CONFIG.beforeEnd > CONFIG.afterStart || CONFIG.beforeStart < '2022-01-01') {
  throw new Error('Use nonoverlapping windows after 2021; JRC baseline contains observations through 2021.');
}
var collection = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(roi)
  .filter(ee.Filter.eq('instrumentMode', 'IW')).filter(ee.Filter.eq('resolution_meters', 10))
  .filter(ee.Filter.eq('orbitProperties_pass', CONFIG.pass))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', CONFIG.relativeOrbit))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', CONFIG.polarization))
  .map(function(img) {
    var angle = img.select('angle');
    return img.select(CONFIG.polarization).updateMask(angle.gt(30).and(angle.lt(45)));
  });
var beforeCollection = collection.filterDate(CONFIG.beforeStart, CONFIG.beforeEnd);
var afterCollection = collection.filterDate(CONFIG.afterStart, CONFIG.afterEnd);
print('Both counts must be positive', beforeCollection.size(), afterCollection.size());
print('Before IDs', beforeCollection.aggregate_array('system:index'));
print('After IDs', afterCollection.aggregate_array('system:index'));
// Empty collections intentionally fail rather than exporting all-clear results.
var before = beforeCollection.median();
var after = afterCollection.median();
var slope = ee.Terrain.slope(ee.Image('USGS/SRTMGL1_003'));
var permanent = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('seasonality').gte(10);
var flood = before.subtract(after).gte(CONFIG.floodDropDb).and(after.lte(CONFIG.floodMaximumDb))
  .and(slope.lte(5)).and(permanent.not()).rename('flood_candidate');
var slides = after.subtract(before).abs().gte(CONFIG.landslideChangeDb)
  .and(slope.gte(15)).rename('slope_change_candidate');
// Lock raster topology to the export grid before connected-component filtering.
flood = flood.reproject({crs: CONFIG.exportCrs, scale: 10});
slides = slides.reproject({crs: CONFIG.exportCrs, scale: 10});
function removeSmall(image) {
  var components = image.selfMask().connectedPixelCount(100, true);
  return image.and(components.unmask(0).gte(CONFIG.minimumConnectedPixels));
}
flood = removeSmall(flood);
slides = removeSmall(slides);

var optical = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi)
  .filterDate(CONFIG.afterStart, CONFIG.afterEnd).map(function(img) {
    var scl = img.select('SCL');
    var clear = scl.neq(0).and(scl.neq(1)).and(scl.neq(3)).and(scl.neq(8))
      .and(scl.neq(9)).and(scl.neq(10)).and(scl.neq(11));
    var r = img.select('B4').multiply(0.0001);
    var g = img.select('B3').multiply(0.0001);
    var n = img.select('B8').multiply(0.0001);
    var water = g.subtract(n).divide(g.add(n)).gt(0).and(scl.eq(6));
    return r.subtract(g).divide(r.add(g)).rename('ndti')
      .updateMask(clear.and(water).and(r.gte(0)).and(g.gte(0)).and(r.add(g).gt(0)));
  });
print('Optical count (cloud-free water coverage may be much smaller)', optical.size());
var ndti = optical.median();
Map.centerObject(roi);
Map.addLayer(flood.selfMask(), {palette: ['2389da']}, 'Flood candidates, unvalidated');
Map.addLayer(slides.selfMask(), {palette: ['e88929']}, 'Slope change candidates, unvalidated');
Map.addLayer(ndti, {min: -0.3, max: 0.3, palette: ['4575b4', 'ffffbf', 'a50026']}, 'NDTI (not NTU)');
Export.image.toDrive({image: flood.addBands(slides).addBands(ndti).toFloat(),
  description: 'event_screening_unvalidated', region: roi,
  crs: CONFIG.exportCrs, scale: 10, maxPixels: 1e9, fileFormat: 'GeoTIFF'});
