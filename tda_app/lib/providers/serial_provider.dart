import 'package:flutter/foundation.dart';
import 'dart:async';
import 'package:flutter_libserialport/flutter_libserialport.dart';

// ---------------------
class SerialProvider extends ChangeNotifier {
  // Connection state
  bool _isConnected = false;
  String? _selectedPort;
  int _selectedBaudRate = 115200;
  
  // Data storage
  final List<String> _dataLog = [];
  final List<SerialDataPoint> _chartData = [];

  // Getters
  bool get isConnected => _isConnected;
  String? get selectedPort => _selectedPort;
  int get selectedBaudRate => _selectedBaudRate;
  List<String> get dataLog => List.unmodifiable(_dataLog);
  List<SerialDataPoint> get chartData => List.unmodifiable(_chartData);

  SerialPort? _port;
  StreamSubscription<Uint8List>? _subscription;
  String _incomingBuffer = '';
  DateTime _lastUpdate = DateTime.now();

// Replaces manual 'availablePorts' list with dynamic port recognition
  List<String> get availablePorts => SerialPort.availablePorts;

  // Available options
// ---------------------
  // final List<String> availablePorts = [
  //   'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8'
  // ];

  
// ---------------------
  final List<int> availableBaudRates = [
    9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600
  ];


// ---------------------
  // Methods
  void setSelectedPort(String? port) {
    _selectedPort = port;
    notifyListeners();
  }


// ---------------------
  void setSelectedBaudRate(int baudRate) {
    _selectedBaudRate = baudRate;
    notifyListeners();
  }


// ---------------------
  Future<void> toggleConnection() async {
    if (_selectedPort == null) return;
      
    if (_isConnected) {
      _subscription?.cancel();
      _port?.close();
      _port = null;
      _isConnected = !_isConnected;
      _addToLog('Disconnected from $_selectedPort');
      notifyListeners();
    } else {
      _port = SerialPort(_selectedPort!);
      if(!_port!.openReadWrite()){
        _addToLog('Connected to $_selectedPort at $_selectedBaudRate baud');
        notifyListeners();
        return;        
      }

      final config = SerialPortConfig()
        ..baudRate = _selectedBaudRate
        ..bits = 8
        ..parity = SerialPortParity.none
        ..stopBits = 1;

      _port!.config = config;

      final reader = SerialPortReader(_port!);
      _subscription = reader.stream.listen(_handleData);

      _isConnected = true;
      _addToLog('Connected to $_selectedPort at $_selectedBaudRate baud');
      notifyListeners(); 
    }
  }

  void _handleData(Uint8List data) {
    _incomingBuffer += String.fromCharCodes(data);

    int newlineIndex;
  while ((newlineIndex = _incomingBuffer.indexOf('\n')) != -1) {
    final line = _incomingBuffer.substring(0, newlineIndex).trim();
    _incomingBuffer = _incomingBuffer.substring(newlineIndex + 1);

    if (line.isNotEmpty) {
      _addToLog(line);
      _addChartPoint(line);
      }
    }
  }

  void _addChartPoint(String line) {
    final value = double.tryParse(line);
    if (value == null) return;

    final now = DateTime.now();
    if (now.difference(_lastUpdate).inMilliseconds < 33) return;
    _lastUpdate = now;

    _chartData.add(SerialDataPoint(timestamp: now, value: value));
    if (_chartData.length > 1000) _chartData.removeAt(0);

    notifyListeners();
  }

  void _addToLog(String message) {
    final timestamp = DateTime.now().toString().substring(11, 19);
    _dataLog.add('[$timestamp] $message');
    if(_dataLog.length > 500) {
      _dataLog.removeRange(0, _dataLog.length - 500);
    }
    notifyListeners();
  }


  void clearLog() {
    _dataLog.clear();
    notifyListeners();
  }
}


// ---------------------
class SerialDataPoint {
  final DateTime timestamp;
  final double value;

  SerialDataPoint({required this.timestamp, required this.value});
}