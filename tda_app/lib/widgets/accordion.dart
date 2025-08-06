import 'package:flutter/material.dart';
import 'package:accordion/accordion.dart';

class ControlPanelAccordion extends StatelessWidget {
  const ControlPanelAccordion({super.key});


  
  static const headerStyle = TextStyle(color: Color(0xffffffff), fontSize: 16, fontWeight: FontWeight.bold);
  static const contentStyleHeader = TextStyle(color: Color(0xff999999), fontSize: 14, fontWeight: FontWeight.w700);
  static const contentStyle = TextStyle(color: Color(0xff999999), fontSize: 14, fontWeight: FontWeight.normal);
  

  @override
  build(context) => Container(
    color: Colors.white10,
    width: double.infinity,
    child: Column(
      children: [
        Container(
          color: Colors.amber[800],
          width: double.infinity,
          height: 56,
          padding: const EdgeInsets.all(10), 
          child: Text('Control Panel', style: TextStyle(color: Colors.black, fontSize: 26, fontWeight: FontWeight.w700), textAlign: TextAlign.center,),
        ),

        // const SizedBox(height: 10,),

        Expanded(
          child: Accordion(
          
            // Sets default colors for accordion header text background when closed and opened
              headerBackgroundColor: Colors.brown,
              headerBackgroundColorOpened: Colors.amber,
            // Sets default border colors when closed and opened
              headerBorderColor: Colors.green,
              headerBorderColorOpened: Colors.red,
            // Thickness of header
              headerBorderWidth: 10,
            // Thickness of content border
              contentBorderWidth: 10,
              scaleWhenAnimating: true,
              openAndCloseAnimation: true,
          
            // padding for the accordion list
              paddingListTop: 0,
              // paddingListBottom: 0,
              paddingListHorizontal: 0,
              paddingBetweenClosedSections: 0,
              paddingBetweenOpenSections: 0,
              headerBorderRadius: 0,
              contentBorderRadius: 0,
            
            
            children: [        
              AccordionSection(
                isOpen: true,
                contentVerticalPadding: 0,
                headerPadding: const EdgeInsets.symmetric(horizontal: 0),
                leftIcon: const Icon(Icons.text_fields_rounded, color: Colors.white,),
                header: const Text('Header 1', style: headerStyle,),
                content: Text('Content 1', style: contentStyle,),
              ),
              AccordionSection(
                header: Text('Header 2', style: headerStyle,),
                content: Text('Content 2', style: contentStyle,),
              ),
              AccordionSection(
                header: Text('Header 3', style: headerStyle,),
                content: Text('Content 3', style: contentStyle,),
              ),
            ],
          ),
        ),
        Container(
          padding: EdgeInsets.all(10),
          color: Colors.deepOrange,
          width: double.infinity,
          child: Text('App Settings', style: TextStyle(color: const Color.fromARGB(230, 255, 255, 255), fontWeight: FontWeight.bold), textAlign: TextAlign.center,),
        )
      ],
    ),
  );
}