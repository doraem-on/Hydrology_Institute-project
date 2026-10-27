/* Run in the Earth Engine Code Editor after importing:
 * roi: verified basin/subbasin ee.Geometry (not an administrative bounding box)
 * fields: ee.FeatureCollection with field_id, rice (0/1), split, block_id,
 *         label_source and label_available_at properties.
 * Outputs are observations for offline fitting; this script makes no accuracy
 * claims. Dates and orbit are experimental controls; check local coverage.
 */
if (typeof roi === 'undefined' || typeof fields === 'undefined') {
  throw new Error('Import verified roi and labelled fields first. See docs/digital_twin.md.');
}
var CONFIG = {
  start: '2024-06-01', end: '2024-11-01',
  relativeOrbit: null, pass: 'DESCENDING',
  seed: 42, samplePixelsPerScene: 5000
};
if (CONFIG.relativeOrbit === null) {
  throw new Error('Set one relativeOrbit after inspecting coverage; do not mix SAR geometries.');
}
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(roi).filterDate(CONFIG.start, CONFIG.end)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('resolution_meters', 10))
  .filter(ee.Filter.eq('orbitProperties_pass', CONFIG.pass))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', CONFIG.relativeOrbit))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));
print('SAR scene count; inspect before starting exports', s1.size());
var months = ee.Date(CONFIG.end).difference(ee.Date(CONFIG.start), 'month').ceil();
var emptySar = ee.Image.constant([0, 0]).rename(['VV', 'VH']).updateMask(ee.Image(0));
var monthlyFields = ee.FeatureCollection(ee.List.sequence(0, months.subtract(1)).map(function(i) {
  var start = ee.Date(CONFIG.start).advance(i, 'month');
  var end = ee.Date(start.advance(1, 'month').millis().min(ee.Date(CONFIG.end).millis()));
  var images = s1.filterDate(start, end).map(function(img) {
    // Incidence-angle screening is not a terrain layover/shadow correction.
    return img.select(['VV', 'VH']).updateMask(img.select('angle').gt(30).and(img.select('angle').lt(45)));
  });
  var composite = ee.ImageCollection.fromImages([emptySar]).merge(images).median();
  return composite.reduceRegions({collection: fields, reducer: ee.Reducer.median(), scale: 20, tileScale: 4})
    .map(function(feature) {
      return feature.set({observed_start: start.format('YYYY-MM-dd'),
        observed_end: end.format('YYYY-MM-dd'), scene_count: images.size(),
        source_id: 'COPERNICUS/S1_GRD', availability_status: 'unverified_historical',
        relative_orbit: CONFIG.relativeOrbit, orbit_pass: CONFIG.pass,
        scene_ids: images.aggregate_array('system:index').join('|')});
    });
})).flatten();
Export.table.toDrive({collection: monthlyFields, description: 'rice_field_sar_observations', fileFormat: 'CSV'});

// MODIS native ~1 km scale: do NOT upsample and claim field-scale information.
var vi = ee.ImageCollection('MODIS/061/MOD13A2').filterBounds(roi)
  .filterDate(CONFIG.start, ee.Date(CONFIG.end).advance(-16, 'day'));
var temperature = ee.ImageCollection('MODIS/061/MOD11A2').filterBounds(roi)
  .filterDate(CONFIG.start, CONFIG.end).map(function(img) {
    var qc = img.select('QC_Day');
    var good = qc.bitwiseAnd(3).eq(0).and(qc.rightShift(2).bitwiseAnd(3).eq(0))
      .and(qc.rightShift(6).bitwiseAnd(3).eq(0));
    return img.select('LST_Day_1km').multiply(0.02).rename('lst_kelvin')
      .updateMask(good).copyProperties(img, ['system:time_start', 'system:index']);
  });
var elevation = ee.Image('USGS/SRTMGL1_003').select('elevation');
var emptyTemperature = ee.Image(0).rename('lst_kelvin').updateMask(ee.Image(0));
var moistureSamples = ee.FeatureCollection(vi.toList(vi.size()).map(function(element) {
  var image = ee.Image(element);
  var start = ee.Date(image.get('system:time_start'));
  var end = start.advance(16, 'day');
  // Only use 8-day composites completely inside the 16-day VI support.
  var matched = temperature.filterDate(start, end.advance(-8, 'day').advance(1, 'second'));
  var ndvi = image.select('NDVI').multiply(0.0001).rename('ndvi')
    .updateMask(image.select('SummaryQA').eq(0));
  var lst = ee.ImageCollection.fromImages([emptyTemperature]).merge(matched).mean();
  var pixels = ndvi.addBands(lst).addBands(elevation).addBands(ee.Image.pixelLonLat())
    .sample({region: roi, projection: image.select('NDVI').projection(), scale: 1000,
      numPixels: CONFIG.samplePixelsPerScene, seed: CONFIG.seed, geometries: false, tileScale: 4});
  return pixels.map(function(f) {return f.set({scene_id: image.get('system:index'),
    observed_start: start.format('YYYY-MM-dd'), observed_end: end.format('YYYY-MM-dd'),
    lst_scene_count: matched.size(), lst_scene_ids: matched.aggregate_array('system:index').join('|'),
    availability_status: 'unverified_historical', source_id: 'MOD13A2.061+MOD11A2.061'});});
})).flatten();
Export.table.toDrive({collection: moistureSamples, description: 'totram_scene_samples', fileFormat: 'CSV'});
Map.centerObject(roi);
Map.addLayer(roi, {}, 'Study boundary');
