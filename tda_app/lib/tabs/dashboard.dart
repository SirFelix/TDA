import 'dart:math' as math;
import 'dart:ui';
// ignore: depend_on_referenced_packages
import 'package:../tda_app/app_state.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:tda_app/graphs/daq_chart_widget.dart';
import 'package:tda_app/widgets/sensor_metric_card.dart';
import 'package:tda_app/widgets/data_table.dart';
// import 'package:syncfusion_flutter_datagrid/datagrid.dart';

// class TractorRawFiltered {
//   final DateTime timestamp;
//   final double raw;
//   final double filtered;

//   TractorRawFiltered(this.timestamp, this.raw, this.filtered);
// }

// class TractorSpeed {
//   final DateTime timestamp;
//   final double speed;

//   TractorSpeed(this.timestamp, this.speed);
// }


class DashboardTab extends StatelessWidget {
  const DashboardTab({super.key});



  @override
  Widget build(BuildContext context) {
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
                        children: const [
                          SensorMetricCard(title: 'Current Time', unit: '', value: '12:41:02'),
                          VerticalDivider(color: Colors.black, thickness: 20,),
                          SensorMetricCard(title: 'DAQ Pressure', unit: 'PSI', value: '2500'),
                          SensorMetricCard(title: 'Pressure', unit: 'hPa', value: '1000'),
                          SensorMetricCard(title: 'Temp', unit: '°C', value: '10'),
                          SensorMetricCard(title: 'Rain', unit: 'mm', value: '0'),
                          SensorMetricCard(title: 'Wind', unit: 'm/s', value: '43'),
                          SensorMetricCard(title: 'Speed', unit: 'm/s', value: '12.5'),
                          SensorMetricCard(title: 'Direction', unit: '°', value: '180'),
                          SensorMetricCard(title: 'Elevation', unit: 'm', value: '5,304'),
                          SensorMetricCard(title: 'Elevation', unit: 'm', value: '5,304'),
                          SensorMetricCard(title: 'Elevation', unit: 'm', value: '5,304'),
                          SensorMetricCard(title: 'Elevation', unit: 'm', value: '5,304'),
                          SensorMetricCard(title: 'Elevation', unit: 'm', value: '5,304'),
                          // ...
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),
                  const DataLogInputTable(),
                  const SizedBox(height: 16),
                 

                  
                  DaqChartWidget<TractorRawFiltered>(
                    title: 'Sensor Data (Raw vs Filtered)',
                    height: 400,
                    backgroundColor: Colors.white60,
                    refreshRateMs: 1000,
                    maxDataPoints: 700,
                    animationDuration: 0,
                    isVisible: true,
                    // dataSource: context.watch<AppState>().tractorData,

                    dataGenerator: () {
                      final now = DateTime.now();
                      final raw = (now.millisecond % 100).toDouble();
                      final filtered = raw * 0.4 + 10; // Example filtering
                      return TractorRawFiltered(timestamp: now, raw: raw, filtered: filtered);
                    },

                    seriesConfigs: [
                      ChartSeriesConfig<TractorRawFiltered>(
                        name: 'Raw',
                        color: Colors.red,
                        xValueMapper: (point, _) => point.timestamp,
                        yValueMapper: (point, _) => point.raw,
                      ),
                      ChartSeriesConfig<TractorRawFiltered>(
                        name: 'Filtered',
                        color: Colors.blue,
                        xValueMapper: (point, _) => point.timestamp,
                        yValueMapper: (point, _) => point.filtered,
                      ),
                    ],
                  ),


                  const SizedBox(height: 4),


                  DaqChartWidget<TractorSpeed>(
                    title: 'Tractor Speed',
                    height: 200,
                    backgroundColor: Colors.white60,
                    refreshRateMs: 1000,
                    maxDataPoints: 700,
                    animationDuration: 0,
                    isVisible: true,
                    // dataSource: context.watch<AppState>().tractorSpeedData,

                    dataGenerator: () {
                      final now = DateTime.now();
                      final speed = (math.Random().nextInt(30)).toDouble();
                      return TractorSpeed(timestamp: now, speed: speed);
                    },
                    
                    seriesConfigs: [
                      ChartSeriesConfig<TractorSpeed>(
                        name: 'Speed',
                        color: Colors.green,
                        xValueMapper: (point, _) => point.timestamp,
                        yValueMapper: (point, _) => point.speed,
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
}


