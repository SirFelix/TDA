import 'package:flutter/material.dart';
import 'package:syncfusion_flutter_charts/charts.dart';
import 'package:provider/provider.dart';
import '../providers/serial_provider.dart';
import '../theme/app_theme.dart';

class ChartWidget extends StatelessWidget {
  const ChartWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return Consumer<SerialProvider>(
      builder: (context, serialProvider, child) {
        return Container(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Chart Header
              Row(
                children: [
                  const Icon(
                    Icons.show_chart,
                    color: AppTheme.accentColor,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Live Data Graph',
                    // style: Theme.of(context).textTheme.headlineSmall,
                    style: TextStyle(color: AppTheme.textPrimary, fontSize: 20)
                  ),

                  const Spacer(),

                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: serialProvider.isConnected 
                          ? AppTheme.successColor.withOpacity(0.2)
                          : AppTheme.textSecondary.withOpacity(0.2),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: serialProvider.isConnected 
                            ? AppTheme.successColor
                            : AppTheme.textSecondary,
                        width: 1,
                      ),
                    ),

                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: serialProvider.isConnected 
                                ? AppTheme.successColor
                                : AppTheme.textSecondary,
                            shape: BoxShape.circle,
                          ),
                        ),

                        const SizedBox(width: 6),
                        
                        Text(
                          serialProvider.isConnected ? 'Connected' : 'Disconnected',
                          style: TextStyle(
                            fontSize: 12,
                            color: serialProvider.isConnected 
                                ? AppTheme.successColor
                                : AppTheme.textSecondary,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // Chart Area
              Expanded(
                child: serialProvider.isConnected
                    ? _buildChart(context, serialProvider)
                    : _buildPlaceholder(context),
              ),

              
            ],
          ),
        );
      },
    );
  }

  Widget _buildChart(BuildContext context, SerialProvider provider) {
    final data = provider.chartData;

    if (data.isEmpty) {
      return _buildPlaceholder(context);
    }

    return SfCartesianChart(
      backgroundColor: Colors.transparent,
      plotAreaBorderWidth: 0,
      zoomPanBehavior: ZoomPanBehavior(
        enablePanning: true,
        enableMouseWheelZooming: true,
      ),
      primaryXAxis: DateTimeAxis(
        axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),

        // intervalType: DateTimeIntervalType.seconds,
        // interval: 2,
        // edgeLabelPlacement: EdgeLabelPlacement.shift,
        // enableAutoIntervalOnZooming: true,

        // initialVisibleMinimum: provider.chartData.isNotEmpty
        //   ? provider.chartData.last.timestamp.subtract(const Duration(seconds: 60))
        //   : null,
        // initialVisibleMaximum: provider.chartData.isNotEmpty
        //   ? provider.chartData.last.timestamp
        //   : null,
      ),
      primaryYAxis: NumericAxis(
        axisLine: const AxisLine(color: AppTheme.borderColor),
        majorGridLines: const MajorGridLines(color: AppTheme.borderColor, width: 0.5),
        labelStyle: const TextStyle(color: AppTheme.textSecondary, fontSize: 11),
      ),
      series: <CartesianSeries>[
        LineSeries<SerialDataPoint, DateTime>(
          dataSource: data,
          xValueMapper: (SerialDataPoint point, _) => point.timestamp,
          yValueMapper: (SerialDataPoint point, _) => point.value,
          color: AppTheme.accentColor,
          width: 2,
          animationDuration: 0,
        ),
      ],
      tooltipBehavior: TooltipBehavior(
        enable: true,
        color: AppTheme.surfaceColor,
        textStyle: const TextStyle(color: AppTheme.textPrimary),
      ),
    );
  }


  Widget _buildPlaceholder(BuildContext context) {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.timeline_outlined,
            size: 64,
            color: AppTheme.textSecondary.withOpacity(0.5),
          ),
          const SizedBox(height: 16),
          Text(
            'Connect to a serial port to view live data',
            style: TextStyle(
              color: AppTheme.textSecondary.withOpacity(0.8),
              fontSize: 16,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Select a COM port and baud rate, then click Connect',
            style: TextStyle(
              color: AppTheme.textSecondary.withOpacity(0.6),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

}

// class ChartData {
//   final double x;
//   final double y;

//   ChartData({required this.x, required this.y});
// }