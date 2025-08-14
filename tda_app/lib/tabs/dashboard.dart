import 'dart:math' as math;
import 'dart:ui';
// ignore: depend_on_referenced_packages
import 'package:../tda_app/app_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/graphs/daq_chart_widget.dart';
import 'package:tda_app/widgets/sensor_metric_card.dart';
// import 'package:tda_app/graphs/generic_chart_widget.dart';
import 'package:tda_app/widgets/data_table.dart';
// import 'package:syncfusion_flutter_datagrid/datagrid.dart';

// class TractorPressure {
//   final DateTime timestamp;
//   final double raw;
//   final double filtered;

//   TractorPressure(this.timestamp, this.raw, this.filtered);
// }

// class TractorSpeed {
//   final DateTime timestamp;
//   final double speed;

//   TractorSpeed(this.timestamp, this.speed);
// }

final meanSpeed = 14.0;
final standardDeviationSpeed = 0.25075;

double nextGaussian({double mean = 0, double standardDeviation = 1}) {
  final randomNum = math.Random();
  double u1 = randomNum.nextDouble();
  double u2 = randomNum.nextDouble();

  while (u1 == 0) {
    u1 = randomNum.nextDouble();
  }

  final z = math.sqrt(-2.0 * math.log(u1)) * math.sin(2.0 * math.pi * u2);
  return mean + standardDeviation * z;
}

class DashboardTab extends StatelessWidget {
  const DashboardTab({super.key});



  @override
  Widget build(BuildContext context) {
    return Consumer<AppState>(
      builder: (context, state, child) {

        final latestDAQPressure = state.tractorData.isNotEmpty
            ? state.tractorData.last.rawPressure.toStringAsFixed(1)
            : '--';
        final latestDAQFilteredPressure = state.tractorData.isNotEmpty
            ? state.tractorData.last.filteredPressure.toStringAsFixed(1)
            : '--';
        final latestTractorSpeed = state.tractorSpeedData.isNotEmpty
            ? state.tractorSpeedData.last.tractorSpeed.toStringAsFixed(2)
            : '--';

        final ScrollController verticalController = ScrollController();
        return Scrollbar(
          controller: verticalController,
          thumbVisibility: true,
          trackVisibility: false,
          interactive: true,
        
          child: SingleChildScrollView(
            controller: verticalController,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 16),
        
                // Wrap actual content in Padding
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0),
                  child: Column(
                    children: [
                      // Scrollable sensor cards
                      ScrollConfiguration(
                        behavior: ScrollConfiguration.of(context).copyWith(
                          scrollbars: true,
                          dragDevices: {
                            PointerDeviceKind.touch,
                            PointerDeviceKind.mouse,
                          },
                        ),
                        child: SingleChildScrollView(
                          scrollDirection: Axis.horizontal,
                          child: Row(
                            children: [

                              StreamBuilder<DateTime>(
                                stream: Stream.periodic(const Duration(seconds: 1), (_) => DateTime.now()),
                                builder: (context, snapshot) {
                                  final now = snapshot.data ?? DateTime.now();
                                  final timeStr = "${now.hour.toString().padLeft(2, '0')}:"
                                                  "${now.minute.toString().padLeft(2, '0')}:"
                                                  "${now.second.toString().padLeft(2, '0')}";
                                  return SensorMetricCard(title: 'Current Time', unit: '', value: timeStr);
                                }
                              ),
                              VerticalDivider(color: Colors.black, thickness: 20,),
                              SensorMetricCard(title: 'DAQ Raw Pressure', unit: 'PSI', value: latestDAQPressure),
                              SensorMetricCard(title: 'DAQ FilteredPressure', unit: 'PSI', value: latestDAQFilteredPressure),
                              SensorMetricCard(title: 'DAQ Speed', unit: 'FPM', value: latestTractorSpeed),
                              SensorMetricCard(title: 'CT Pressure', unit: 'PSI', value: state.rigData.isNotEmpty ? state.rigData.last.ctPressure.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'WH Pressure', unit: 'PSI', value: state.rigData.isNotEmpty ? state.rigData.last.whPressure.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'CT Depth', unit: 'FT', value: state.rigData.isNotEmpty ? state.rigData.last.ctDepth.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'CT Weight', unit: 'LBS', value: state.rigData.isNotEmpty ? state.rigData.last.ctWeight.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'CT Speed', unit: 'FPM', value: state.rigData.isNotEmpty ? state.rigData.last.ctSpeed.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'CT FL Rate', unit: 'BPM', value: state.rigData.isNotEmpty ? state.rigData.last.ctFluidRate.toStringAsFixed(1) : '--'),
                              SensorMetricCard(title: 'N2 FL Rate', unit: 'SCF', value: state.rigData.isNotEmpty ? state.rigData.last.n2FluidRate.toStringAsFixed(1) : '--'),


                            // // For static mock data
                              // // SensorMetricCard(title: 'Current Time', unit: '', value: '12:41:02'),
                              // VerticalDivider(color: Colors.black, thickness: 20,),
                              // SensorMetricCard(title: 'DAQ Pressure', unit: 'PSI', value: '5,461'),
                              // SensorMetricCard(title: 'Est. Tractor Speed', unit: 'FPM', value: '14.7'),
                              // SensorMetricCard(title: 'Circ Pressure', unit: 'PSI', value: '6,492'),
                              // SensorMetricCard(title: 'WH Pressure', unit: 'PSI', value: '1,735'),
                              // SensorMetricCard(title: 'CT Depth', unit: 'FT', value: '18,743.4'),
                              // SensorMetricCard(title: 'CT Weight', unit: 'LBS', value: '15,461'),
                              // SensorMetricCard(title: 'CT Speed', unit: 'FPM', value: '14.5'),
                              // SensorMetricCard(title: 'CT FL Rate', unit: 'BPM', value: '5.72'),
                              // SensorMetricCard(title: 'N2 FL Rate', unit: 'SCF', value: '0.00'),
                            // -------------------------------------
                            ],
                          ),
                        ),
                      ),
        
                      const SizedBox(height: 16),
                      const Text('Operations Log', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 25)),
                      const SizedBox(height: 16),

                      const LoggingTable(listHeight: 100,),
                      const SizedBox(height: 16),


                    
        
                      // for the raw pressure and filtered pressure
                      DaqChartWidget<TractorPressure>(
                        title: 'Sensor Data (Raw vs Filtered)',
                        height: 400,
                        backgroundColor: Colors.white60,
                        refreshRateMs: 500,
                        maxDataPoints: 1500,
                        animationDuration: 0,
                        isVisible: true,
                        dataSource: context.watch<AppState>().tractorData,
        
                        // dataGenerator: () {
                        //   final now = DateTime.now();
                        //   final raw = (now.millisecond % 100).toDouble();
                        //   final filtered = raw * 0.4 + 15; // Example filtering
                        //   return TractorPressure(timestamp: now, rawPressure: raw, filteredPressure: filtered);
                        // },
        
                        seriesConfigs: [
                          ChartSeriesConfig<TractorPressure>(
                            name: 'Raw',
                            color: Colors.grey[300]!,
                            xValueMapper: (point, _) => point.timestamp,
                            yValueMapper: (point, _) => point.rawPressure,
                          ),
                          ChartSeriesConfig<TractorPressure>(
                            name: 'Filtered',
                            color: Colors.blue,
                            xValueMapper: (point, _) => point.timestamp,
                            yValueMapper: (point, _) => point.filteredPressure,
                          ),
                        ],
                      ),

        
                      // GenericChartWidget<TractorPressure>(
                      //   isConnected: context.watch<AppState>().isDAQConnected,
                      //   title: 'DAQ Chart',
                      //   icon: Icons.stacked_line_chart,
                      //   data: context.watch<AppState>().tractorData,
                      //   // xValueMapper: (p) => p.timestamp,
                      //   // yValueMapper: (p) => p.value,
                      //   xValueMapper: (point, _) => point.timestamp,
                      //   yValueMapper: (point, _) => point.raw,
                      //   placeholderTitle: 'Connect to an NI Module to view live data',
                      //   placeholderHint: 'Select a Sampling Rate (Hz) then click Start DAQ',
                      // ),
        
        
                      const SizedBox(height: 18),
                      const Text('Estimated Tractor Speed', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 25)),
                      const SizedBox(height: 4),
        


                      // for 
                      DaqChartWidget<TractorSpeed>(
                        title: 'Tractor Speed',
                        // height: 200,
                        backgroundColor: Colors.white60,
                        refreshRateMs: 250,
                        maxDataPoints: 300,
                        animationDuration: 0,
                        isVisible: true,

                        dataSource: context.watch<AppState>().tractorSpeedData,
        
                        // // Only used if dataSource is not declared
                        // dataGenerator: () {
                        //   final now = DateTime.now();
                        //   // final speed = (13.0 + math.Random().nextInt(2)).toDouble();
                        //   final speed = nextGaussian(mean: meanSpeed, standardDeviation: standardDeviationSpeed);
                        //   return TractorSpeed(timestamp: now, tractorSpeed: speed);
                        // },
                        
                        seriesConfigs: [
                          ChartSeriesConfig<TractorSpeed>(
                            name: 'Speed',
                            color: Colors.deepOrange,
                            xValueMapper: (point, _) => point.timestamp,
                            yValueMapper: (point, _) => point.tractorSpeed,
                          ),
                        ],
                      ),
                      // const DaqChartWidget(),
                    ],
                  ),
                ),
        
                const SizedBox(height: 16),
              ],
            ),
          ),
        );
      }
    );

  }
}


