'use client';
import { BorderBeam } from "@/components/ui/border-beam";
import styles from "../page.module.css";
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@radix-ui/react-label";
import { Input } from "@/components/ui/input";
import Meteors from "@/components/ui/meteors";
import { resData } from "./data"
import ReactJson from "react-json-view";
import { Drawer, DrawerClose, DrawerContent, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle, DrawerTrigger } from "@/components/ui/drawer";
import { ScrollArea } from "@/components/ui/scroll-area";
import jsPDF from "jspdf";
import ShinyButton from "@/components/ui/shiny-button";
import PulsatingButton from "@/components/ui/pulsating-button";

export default function Home() {

    const [url, setURL] = useState('');
    const [fetched, setFetch] = useState(false);
    const [response, setResponse] = useState({});
    const baseURL = "http://a28a61c6c48bb417897f06ced9d58895-167885905.us-west-2.elb.amazonaws.com/zap/basescan";

    let lineNumber = 10;
    let pageHeight = 0;
    const router = useRouter()

    const printPDF = (doc: jsPDF, obj: object) => {
        for (let key in obj) {
            if (typeof (obj[key]) === "string") {
                // console.log(obj[key]);

                if (lineNumber + 10 > pageHeight - 10) {
                    doc.addPage();
                    lineNumber = 10;
                }

                const result = `${key} : ${obj[key]}`;
                var dim = doc.getTextDimensions(result, { maxWidth: 180 });
                doc.text(result, 10, lineNumber, { maxWidth: 180 });

                lineNumber = lineNumber + dim.h;

            } else if (Array.isArray(obj[key])) {
                if (lineNumber + 10 > pageHeight - 10) {
                    doc.addPage();
                    lineNumber = 10;
                }

                const result = `${key} :  is of type Array with index described below`;
                doc.text(result, 10, lineNumber);
                lineNumber = lineNumber + 10;

                printPDF(doc, obj[key]);

            } else {
                if (lineNumber + 10 > pageHeight - 10) {
                    doc.addPage();
                    lineNumber = 10;
                }

                const result = `${key} : is of type object described below `;
                doc.text(result, 10, lineNumber);
                lineNumber = lineNumber + 10;

                printPDF(doc, obj[key]);
            }
        }


    }

    const downloadPdf = () => {
        const doc = new jsPDF();
        pageHeight = doc.internal.pageSize.height;

        // const jsonData = JSON.stringify(resData);

        // Title
        doc.setFontSize(12);

        printPDF(doc, response);


        const pdfBlob = doc.output("blob");

        // Create a URL for the Blob
        const pdfUrl = URL.createObjectURL(pdfBlob);

        // Open the PDF in a new tab
        window.open(pdfUrl, "_blank");

        // Save the PDF
        // doc.save("data.pdf");
    };

    // const saveData = (doc, line) => {
    //     let obj = JSON.stringify(line);
    //     if(obj)
    // }
    const movePagetoChatAI = () => {
        sessionStorage.setItem("data", JSON.stringify(response));
        router.push("/chatUI");

    }


    useEffect(() => {

        const helperFunction = async (value: string) => {


            // const params = new URLSearchParams({
            //     'target_url': value
            // });
            // console.log(params);
            // const fetchURL = baseURL + '?' + params;
            // console.log(fetchURL);

            // const res = await fetch(`${baseURL}?${params}`, {
            //     method: 'POST',
            //     headers: {
            //         'Content-Type': 'application/json',
            //     }
            // });

            // console.log(res);

            // setResponse(await res.json());
            // console.log(response);


            // setFetch(true);



            setTimeout(() => {
                setResponse(resData);
                setFetch(true);
            }, 1000);

        }
        // Retrieve data from the browser's history state
        const value = sessionStorage.getItem('url');
        console.log(value); // Outputs: 'value'

        if (value && !fetched) {
            setURL(value);
            //   sessionStorage.removeItem('url');
            helperFunction(value);




        }

    }, []);

    return (
        <div className={styles.background2}>


            {fetched ?

                <>
                    <div className={styles.page1}>
                        <main className={styles.main}>

                            <div className="relative flex h-[500px] w-[1000px] flex-col items-center justify-center overflow-hidden rounded-lg border bg-background md:shadow-xl">
                                <h2> Results have been received</h2>
                                <ScrollArea className="h-500px w-1000px rounded-md border">


                                    <ReactJson src={response} theme="monokai" />

                                </ScrollArea>
                            </div>

                            <div className="flex space-x-200 gap-[40px] items-center justify-center">
                                <PulsatingButton onClick={downloadPdf}>Download the PDF report</PulsatingButton>
                                <PulsatingButton onClick={movePagetoChatAI}>Connect with a ChatBot</PulsatingButton>
                            </div>

                        </main>

                    </div>





                </>


                :


                <>
                    <div className={styles.page}>
                        <main className={styles.main}>
                            <div className="relative flex h-[350px] w-[500px] flex-col items-center justify-center overflow-hidden rounded-lg border bg-background md:shadow-xl">

                                <span className="pointer-events-none whitespace-pre-wrap bg-gradient-to-b from-black to-gray-300/80 bg-clip-text text-center text-6xl font-semibold leading-none text-transparent dark:from-white dark:to-slate-900/10">
                                    Fetching
                                </span>
                                <BorderBeam size={250} duration={12} delay={9} />
                                <Meteors number={100} />

                            </div>
                        </main>

                    </div>


                </>

            }










        </div >
    );
}
