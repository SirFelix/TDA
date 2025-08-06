import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:tda_app/app_state.dart';
import 'package:accordion/controllers.dart';
// import 'package:flutter_slider_drawer/flutter_slider_drawer.dart';
import 'package:tda_app/main_screen.dart';

void main() {
  AppState().init();
  Get.put(ListController());
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Flutter Demo',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent),
      ),
      debugShowCheckedModeBanner: false,
      home: const MainScreen(),
    );
  }
}


