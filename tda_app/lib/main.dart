import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'app_state.dart';
import 'main_screen.dart';
// import 'package:get/get.dart';
// import 'package:accordion/controllers.dart';

// void main() {
//   AppState().init();
//   Get.put(ListController());
//   runApp(const MyApp());
// }

void main(){
  runApp(
    ChangeNotifierProvider(
      create: (_){
      final state = AppState();
      state.init();
      return state;
      },
      child: const MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  // This widget is the root of your application.
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Tractor Data Analyzer',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueAccent),
      ),
      debugShowCheckedModeBanner: false,
      home: const MainScreen(),
    );
  }
}


